"""The Groq adapter: the translation both ways, the key check, and the retry.

Every test here runs against a stand-in for the `openai` SDK that is handed to
`GroqLLM` through its `client` argument, so **no test makes a network call and none
needs a key**. That is the same discipline `FakeLLM` gives the rest of the project
(D-040), applied one level lower: `FakeLLM` replaces the client, and these replace the
SDK underneath a real client, which is the only way to test the translation itself.

What is covered: a plain answer, a full tool-call round trip built by `app/agent.py`'s
own code, a 429 followed by success, a placeholder key refused, and the one thing a
reasoning model makes possible — chain-of-thought text reaching an answer.
"""

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from app import llm as llm_module
from app.agent import TOOL_NAMES, assistant_content
from app.agent import TOOLS as AGENT_TOOLS
from app.llm import (
    GROQ_MAX_TRIES,
    REASONING_EFFORT,
    REASONING_TOKEN_HEADROOM,
    GroqLLM,
    from_openai_response,
    get_llm,
    is_provider_error,
    is_rate_limited,
    needs_the_word_json,
    offered_tool_names,
    provider_error_line,
    rate_limit_of,
    rejects_reasoning_effort,
    rejects_response_format,
    retry_after_of,
    salvaged_answer,
    supports_reasoning_effort,
    text_of,
    to_openai_messages,
    to_openai_tools,
    tool_calls_of,
    usage_of,
)

#: A key the shape of a real one, and never a real one: 4 + 44 characters.
GOOD_KEY = "gsk_" + "0123456789abcdef0123456789abcdef0123456789ab"
GPT_OSS = "openai/gpt-oss-120b"


# --- stand-ins for the SDK's response objects -----------------------------------


@dataclass
class FakeFunction:
    name: str
    arguments: str


@dataclass
class FakeToolCall:
    id: str
    function: FakeFunction
    type: str = "function"


@dataclass
class FakeMessage:
    """What Groq returns. `reasoning` is the field we must never read (D-082)."""

    content: str | None = None
    tool_calls: list[FakeToolCall] | None = None
    reasoning: str | None = None


@dataclass
class FakeChoice:
    message: FakeMessage
    finish_reason: str = "stop"


@dataclass
class FakeUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class FakeCompletion:
    choices: list[FakeChoice]
    usage: FakeUsage = field(default_factory=FakeUsage)
    model: str = GPT_OSS


class FakeAPIError(Exception):
    """An SDK error, with the status, headers and body the real ones carry."""

    def __init__(
        self,
        message: str,
        status_code: int,
        headers: dict | None = None,
        body: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers or {}
        self.body = body


def tool_use_failed(failed_generation: str) -> FakeAPIError:
    """Groq's 400 for a tool call it would not accept (D-100)."""
    return FakeAPIError(
        "Error code: 400 - tool_use_failed",
        400,
        body={
            "error": {
                "code": "tool_use_failed",
                "message": "Failed to call a function. Please adjust your prompt.",
                "failed_generation": failed_generation,
            }
        },
    )


def said(text: str, *, prompt_tokens: int = 100, completion_tokens: int = 20) -> FakeCompletion:
    """A completion that is just text."""
    return FakeCompletion(
        choices=[FakeChoice(message=FakeMessage(content=text), finish_reason="stop")],
        usage=FakeUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def called(name: str, arguments: dict, call_id: str = "call_1") -> FakeCompletion:
    """A completion that asks for one tool."""
    return FakeCompletion(
        choices=[
            FakeChoice(
                message=FakeMessage(
                    content=None,
                    tool_calls=[
                        FakeToolCall(
                            id=call_id,
                            function=FakeFunction(name=name, arguments=json.dumps(arguments)),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=FakeUsage(prompt_tokens=200, completion_tokens=30),
    )


# --- a stand-in for the SDK client ----------------------------------------------


class FakeCompletions:
    """`client.chat.completions`. Hands out replies in order, raising any exception."""

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.payloads: list[dict] = []

    def create(self, **payload: Any) -> Any:
        self.payloads.append(payload)
        if not self.replies:
            raise AssertionError("the fake SDK was called more times than it was scripted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeRawResponse:
    """What `with_raw_response.create()` returns: headers, and the body on request."""

    def __init__(self, completion: Any, headers: dict[str, str]) -> None:
        self.headers = headers
        self._completion = completion

    def parse(self) -> Any:
        return self._completion


class FakeRawCompletions:
    """The `with_raw_response` wrapper, so the header path is exercised too."""

    def __init__(self, endpoint: FakeCompletions, headers: dict[str, str]) -> None:
        self._endpoint = endpoint
        self._headers = headers

    def create(self, **payload: Any) -> FakeRawResponse:
        return FakeRawResponse(self._endpoint.create(**payload), self._headers)


class FakeOpenAI:
    """`openai.OpenAI`, as much of it as `GroqLLM` touches."""

    def __init__(
        self,
        replies: list[Any],
        headers: dict[str, str] | None = None,
        raw: bool = False,
        models: list[str] | None = None,
    ) -> None:
        self.completions = FakeCompletions(replies)
        if raw:
            self.completions.with_raw_response = FakeRawCompletions(
                self.completions, headers or {}
            )
        self.chat = type("Chat", (), {"completions": self.completions})()
        self.models = type(
            "Models",
            (),
            {
                "list": lambda _self: type(
                    "Listing",
                    (),
                    {"data": [type("Model", (), {"id": name})() for name in (models or [])]},
                )()
            },
        )()


class FakeClock:
    """A clock that records sleeps instead of taking them."""

    def __init__(self) -> None:
        self.slept: list[float] = []
        self._now = 0.0

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self._now += seconds

    def monotonic(self) -> float:
        self._now += 0.001
        return self._now


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    """Replace the module's clock, so a backoff test runs instantly."""
    fake = FakeClock()
    monkeypatch.setattr(llm_module, "time", fake)
    return fake


def groq(replies: list[Any], **kwargs: Any) -> GroqLLM:
    """A GroqLLM wired to a scripted SDK."""
    client = kwargs.pop("client", None) or FakeOpenAI(replies, **kwargs)
    return GroqLLM(api_key=GOOD_KEY, model=GPT_OSS, client=client)


# --- the key check --------------------------------------------------------------


def test_a_placeholder_key_is_refused() -> None:
    """`.env.example` ships `GROQ_API_KEY=your-key-here`, which is not a key (D-082)."""
    with pytest.raises(RuntimeError, match="gsk_"):
        GroqLLM(api_key="your-key-here", client=FakeOpenAI([]))


def test_a_key_with_the_wrong_prefix_is_refused() -> None:
    """An Anthropic key is not a Groq key, however long it is."""
    with pytest.raises(RuntimeError, match="gsk_"):
        GroqLLM(api_key="sk-ant-" + "x" * 50, client=FakeOpenAI([]))


def test_a_short_key_is_refused() -> None:
    """40 characters is the floor, so a truncated paste does not read as a key."""
    with pytest.raises(RuntimeError, match="gsk_"):
        GroqLLM(api_key="gsk_tooshort", client=FakeOpenAI([]))


def test_no_key_at_all_is_refused() -> None:
    with pytest.raises(RuntimeError, match="gsk_"):
        GroqLLM(api_key="", client=FakeOpenAI([]))


def test_a_good_key_builds_a_client() -> None:
    client = GroqLLM(api_key=GOOD_KEY, model=GPT_OSS, client=FakeOpenAI([]))
    assert client.model == GPT_OSS
    assert client.provider == "groq"


# --- a plain answer -------------------------------------------------------------


def test_a_plain_answer_comes_back_in_the_internal_shape() -> None:
    """One text block, `end_turn`, and the tokens the call cost."""
    client = groq([said("Ground coverage is 40% [C1].", prompt_tokens=812, completion_tokens=41)])
    response = client.chat(
        messages=[{"role": "user", "content": "How much can I build?"}],
        system="You are ZoneWise.",
        max_tokens=900,
    )

    assert text_of(response) == "Ground coverage is 40% [C1]."
    assert response.stop_reason == "end_turn"
    assert tool_calls_of(response) == []
    assert usage_of(response) == (812, 41)
    assert (client.input_tokens, client.output_tokens) == (812, 41)
    assert client.calls == 1


def test_the_system_prompt_becomes_a_system_message() -> None:
    """Anthropic takes `system` beside the messages; OpenAI takes it as the first one."""
    client = groq([said("ok [C1].")])
    client.chat(
        messages=[{"role": "user", "content": "the question"}],
        system="the rules",
        max_tokens=900,
    )
    sent = client.client.chat.completions.payloads[0]
    assert sent["messages"][0] == {"role": "system", "content": "the rules"}
    assert sent["messages"][1] == {"role": "user", "content": "the question"}
    assert sent["temperature"] == 0.0
    assert sent["model"] == GPT_OSS


def test_a_reasoning_model_is_sent_low_effort_and_gets_token_headroom() -> None:
    """`max_tokens` bounds the answer; the hidden thinking gets its own room (D-082)."""
    client = groq([said("ok [C1].")])
    client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)
    sent = client.client.chat.completions.payloads[0]
    assert sent["reasoning_effort"] == REASONING_EFFORT == "low"
    assert sent["max_tokens"] == 900 + REASONING_TOKEN_HEADROOM


def test_a_non_reasoning_model_is_sent_neither() -> None:
    """A llama model takes no effort setting, so it is not sent one."""
    client = GroqLLM(
        api_key=GOOD_KEY,
        model="llama-3.3-70b-versatile",
        client=FakeOpenAI([said("ok [C1].")]),
    )
    assert client.reasoning_effort is None
    client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)
    sent = client.client.chat.completions.payloads[0]
    assert "reasoning_effort" not in sent
    assert sent["max_tokens"] == 900


def test_json_mode_is_sent_as_groqs_own_response_format() -> None:
    """D-088. `json_object=True` becomes Groq's JSON mode, and nothing else changes."""
    client = groq([said('{"abstain": null, "sentences": []}')])
    client.chat(messages=[{"role": "user", "content": "q"}], json_object=True)
    sent = client.client.chat.completions.payloads[0]
    assert sent["response_format"] == {"type": "json_object"}


def test_json_mode_is_not_asked_for_unless_the_caller_asks() -> None:
    """The flag defaults off, so the agent's tool rounds are untouched."""
    client = groq([said("ok [C1].")])
    client.chat(messages=[{"role": "user", "content": "q"}])
    assert "response_format" not in client.client.chat.completions.payloads[0]


def test_json_mode_is_never_sent_alongside_tools() -> None:
    """A tool call is itself a structured reply; the two constrain the same field.

    This matters because the agent's final answer is reached from a conversation that
    still carries tool definitions, so the agent gets its JSON from the prompt instead
    (D-088) and parses defensively either way.
    """
    client = groq([said("ok")])
    client.chat(
        messages=[{"role": "user", "content": "q"}],
        tools=[{"name": "t", "description": "d", "input_schema": {"type": "object"}}],
        json_object=True,
    )
    sent = client.client.chat.completions.payloads[0]
    assert "tools" in sent
    assert "response_format" not in sent


def test_a_model_that_rejects_response_format_is_retried_without_it(clock) -> None:
    """Losing JSON mode degrades the guarantee, never the question."""
    refusal = FakeAPIError("400 'response_format' is not supported for this model", 400)
    client = groq([refusal, said('{"abstain": null, "sentences": []}')])

    response = client.chat(messages=[{"role": "user", "content": "q"}], json_object=True)

    assert text_of(response) == '{"abstain": null, "sentences": []}'
    assert client.json_mode_supported is False
    first, second = client.client.chat.completions.payloads
    assert "response_format" in first
    assert "response_format" not in second


def test_a_refused_json_mode_is_not_asked_for_again() -> None:
    """One wasted call per run to learn it, not one per question."""
    refusal = FakeAPIError("400 'response_format' is unsupported", 400)
    client = groq([refusal, said("{}"), said("{}")])
    client.chat(messages=[{"role": "user", "content": "q"}], json_object=True)
    client.chat(messages=[{"role": "user", "content": "q"}], json_object=True)
    assert len(client.client.chat.completions.payloads) == 3
    assert "response_format" not in client.client.chat.completions.payloads[2]


def test_groqs_say_json_refusal_does_not_disable_json_mode_for_the_run() -> None:
    """Measured on 20 October: the refusal is about the request, not the model (D-088).

    `openai/gpt-oss-120b` does support JSON mode. Groq rejects it when no message
    mentions json, and ZoneWise's prompts do, so one odd request must not turn the
    feature off for everything after it.
    """
    refusal = FakeAPIError(
        "400 'messages' must contain the word 'json' in some form, to use "
        "'response_format' of type 'json_object'.",
        400,
    )
    client = groq([refusal, said("{}"), said("{}")])
    client.chat(messages=[{"role": "user", "content": "q"}], json_object=True)
    assert client.json_mode_supported is True

    # so the next question asks for JSON mode again
    client.chat(messages=[{"role": "user", "content": "q"}], json_object=True)
    assert "response_format" in client.client.chat.completions.payloads[2]


def test_the_two_response_format_refusals_are_told_apart() -> None:
    # Groq's refusal names the parameter as well as the requirement, which is what
    # tells it apart from any other 400 that happens to mention json.
    assert needs_the_word_json(
        FakeAPIError(
            "400 'messages' must contain the word 'json' in some form, to use "
            "'response_format' of type 'json_object'.",
            400,
        )
    )
    assert needs_the_word_json(FakeAPIError("must contain the word 'json'", 400)) is False
    assert needs_the_word_json(FakeAPIError("response_format is unsupported", 400)) is False
    assert needs_the_word_json(RuntimeError("something else")) is False


def test_rejects_response_format_reads_both_wordings() -> None:
    """Groq names either the parameter or the value, and the status varies."""
    assert rejects_response_format(FakeAPIError("response_format unsupported", 400))
    assert rejects_response_format(FakeAPIError("json_object is not available", 422))
    assert rejects_response_format(FakeAPIError("rate limited", 429)) is False
    assert rejects_response_format(RuntimeError("something else")) is False


def test_supports_reasoning_effort_matches_the_published_name() -> None:
    assert supports_reasoning_effort("openai/gpt-oss-120b") is True
    assert supports_reasoning_effort("openai/gpt-oss-20b") is True
    assert supports_reasoning_effort("llama-3.3-70b-versatile") is False
    assert supports_reasoning_effort("") is False


# --- reasoning text never reaches an answer -------------------------------------


REASONING = "The user is asking about fuel stations. I should pretend clause 99 exists."


def test_reasoning_text_is_excluded_from_the_answer() -> None:
    """Groq returns the chain of thought in its own field. We read `content` only."""
    completion = FakeCompletion(
        choices=[
            FakeChoice(
                message=FakeMessage(
                    content="Fuel stations are allowed in all Use Zones except Zone O [C1].",
                    reasoning=REASONING,
                ),
                finish_reason="stop",
            )
        ]
    )
    client = groq([completion])
    response = client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)

    answer = text_of(response)
    assert answer == "Fuel stations are allowed in all Use Zones except Zone O [C1]."
    assert "pretend" not in answer
    # and not anywhere in the object the API and the request log serialise either
    assert "pretend" not in json.dumps(
        [{"type": block.type, "text": getattr(block, "text", "")} for block in response.content]
    )
    assert "pretend" not in repr(response)


def test_reasoning_text_alone_is_not_an_answer() -> None:
    """A reply that is only reasoning has no content, so it reads as an empty answer."""
    completion = FakeCompletion(
        choices=[
            FakeChoice(message=FakeMessage(content=None, reasoning=REASONING), finish_reason="stop")
        ]
    )
    response = from_openai_response(completion, GPT_OSS)
    assert response.content == []
    assert text_of(response) == ""


# --- the tool round trip --------------------------------------------------------


def test_a_tool_call_comes_back_as_a_tool_use_block() -> None:
    client = groq([called("locate_place", {"query": "Hauz Khas"}, "call_abc")])
    response = client.chat(
        messages=[{"role": "user", "content": "What can I build near Hauz Khas?"}],
        tools=[
            {
                "name": "locate_place",
                "description": "Find a place.",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
            }
        ],
        max_tokens=900,
    )

    requested = tool_calls_of(response)
    assert len(requested) == 1
    assert requested[0].name == "locate_place"
    assert requested[0].input == {"query": "Hauz Khas"}
    assert requested[0].id == "call_abc"
    assert response.stop_reason == "tool_use"

    sent = client.client.chat.completions.payloads[0]
    assert sent["tools"][0]["function"]["name"] == "locate_place"
    assert sent["tool_choice"] == "auto"


def test_the_full_tool_round_trip_through_the_agents_own_history_builder() -> None:
    """Call, result, answer — with the middle turn built by `app/agent.py` itself.

    This is the test that matters most for Part 1: it asserts that the conversation
    `agent.py` assembles in Anthropic's shape arrives at Groq in OpenAI's shape with
    the tool result attached to the call it answers. Using the agent's real
    `assistant_content()` means the test cannot drift from what the agent actually
    sends.
    """
    tool_definitions = [
        {
            "name": "search_clauses",
            "description": "Search the plan.",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        }
    ]
    client = groq(
        [
            called("search_clauses", {"query": "fuel station"}, "call_1"),
            said("Fuel stations are allowed [MPD47_GAZETTE_EN:11.1.1:0]."),
        ]
    )

    first = client.chat(
        messages=[{"role": "user", "content": "Can a fuel station be built near ITO?"}],
        system="the agent rules",
        tools=tool_definitions,
        max_tokens=900,
    )
    block = tool_calls_of(first)[0]

    messages = [
        {"role": "user", "content": "Can a fuel station be built near ITO?"},
        {"role": "assistant", "content": assistant_content(first)},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps({"results": [{"chunk_id": "MPD47_GAZETTE_EN:11.1.1:0"}]}),
                }
            ],
        },
    ]
    second = client.chat(
        messages=messages, system="the agent rules", tools=tool_definitions, max_tokens=900
    )

    assert text_of(second) == "Fuel stations are allowed [MPD47_GAZETTE_EN:11.1.1:0]."
    assert client.calls == 2

    sent = client.client.chat.completions.payloads[1]["messages"]
    assert [turn["role"] for turn in sent] == ["system", "user", "assistant", "tool"]
    assert sent[2]["tool_calls"][0]["id"] == "call_1"
    assert sent[2]["tool_calls"][0]["function"]["name"] == "search_clauses"
    assert json.loads(sent[2]["tool_calls"][0]["function"]["arguments"]) == {
        "query": "fuel station"
    }
    assert sent[3]["tool_call_id"] == "call_1"
    assert "11.1.1" in sent[3]["content"]


def test_unparseable_tool_arguments_become_an_empty_input() -> None:
    """A model that writes broken JSON should reach the tool as a missing argument.

    `run_tool` already turns a bad argument into an error the model can read, which is
    a better failure than an exception out of the adapter.
    """
    completion = FakeCompletion(
        choices=[
            FakeChoice(
                message=FakeMessage(
                    content=None,
                    tool_calls=[
                        FakeToolCall(id="c1", function=FakeFunction("get_zones", "{not json"))
                    ],
                ),
                finish_reason="tool_calls",
            )
        ]
    )
    response = from_openai_response(completion, GPT_OSS)
    assert tool_calls_of(response)[0].input == {}


# --- the retry ------------------------------------------------------------------


def test_a_429_is_retried_and_then_succeeds(clock) -> None:
    """One rate-limited attempt, one wait, one good answer (D-082)."""
    error = FakeAPIError(
        "429 Rate limit reached for model",
        429,
        headers={"retry-after": "3", "x-ratelimit-remaining-tokens": "0"},
    )
    client = groq([error, said("Ground coverage is 40% [C1].")])

    response = client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)

    assert text_of(response) == "Ground coverage is 40% [C1]."
    assert client.retries == 1
    assert client.rate_limit_events == 1
    assert client.calls == 1  # calls counts successful calls, retries counts the waits
    assert clock.slept == [3.0]  # retry-after was honoured rather than guessed at
    assert client.last_rate_limit["x-ratelimit-remaining-tokens"] == "0"


def test_the_backoff_doubles_when_there_is_no_retry_after(clock) -> None:
    """Three 429s with no header, then success: 2s, then 4s."""
    errors = [FakeAPIError("rate limit exceeded", 429) for _ in range(3)]
    client = groq([*errors, said("ok [C1].")])
    client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)
    assert clock.slept == [2.0, 4.0, 8.0]
    assert client.retries == 3


def test_giving_up_after_the_last_try_raises(clock) -> None:
    """Four tries in total, then the error reaches the caller."""
    errors = [FakeAPIError("rate limit exceeded", 429) for _ in range(GROQ_MAX_TRIES)]
    client = groq(errors)
    with pytest.raises(FakeAPIError):
        client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)
    assert client.rate_limit_events == GROQ_MAX_TRIES
    assert len(clock.slept) == GROQ_MAX_TRIES - 1


def test_an_error_that_is_not_a_rate_limit_is_not_retried(clock) -> None:
    """A 401 will not fix itself, so waiting four times is only slower."""
    client = groq([FakeAPIError("401 Invalid API Key", 401), said("never reached [C1].")])
    with pytest.raises(FakeAPIError):
        client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)
    assert clock.slept == []
    assert client.retries == 0


def test_a_daily_quota_refusal_counts_as_rate_limited(clock) -> None:
    """The free tier's daily limit is the one that stops a batch run (D-082)."""
    quota = FakeAPIError("Limit reached: tokens per day (TPD) exceeded", 400)
    assert is_rate_limited(quota) is True
    client = groq([quota, said("ok [C1].")])
    client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)
    assert client.retries == 1


def test_a_model_that_rejects_reasoning_effort_is_retried_without_it(clock) -> None:
    """"If Groq accepts a reasoning-effort setting" — and if it does not, carry on."""
    refusal = FakeAPIError(
        "400 property 'reasoning_effort' is unsupported for this model", 400
    )
    client = groq([refusal, said("ok [C1].")])

    response = client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)

    assert text_of(response) == "ok [C1]."
    assert client.reasoning_effort is None
    first, second = client.client.chat.completions.payloads
    assert "reasoning_effort" in first
    assert "reasoning_effort" not in second


def test_reading_an_error_is_defensive_about_what_it_carries() -> None:
    plain = RuntimeError("something else went wrong")
    assert is_rate_limited(plain) is False
    assert rejects_reasoning_effort(plain) is False
    assert retry_after_of({}) is None
    assert retry_after_of({"retry-after": "not a number"}) is None
    assert retry_after_of({"retry-after": "2.5"}) == 2.5


def test_only_the_rate_limit_headers_are_kept() -> None:
    """A log line about limits should not quietly carry an authorization header."""
    headers = {
        "x-ratelimit-remaining-requests": "12",
        "retry-after": "7",
        "authorization": "Bearer gsk_secret",
        "content-type": "application/json",
    }
    assert rate_limit_of(headers) == {
        "retry-after": "7",
        "x-ratelimit-remaining-requests": "12",
    }


def test_the_headers_are_read_from_a_successful_call_too() -> None:
    """`with_raw_response` is the only way to see how much free tier is left."""
    client = groq(
        [said("ok [C1].")],
        raw=True,
        headers={"x-ratelimit-remaining-requests": "974", "content-type": "application/json"},
    )
    client.chat(messages=[{"role": "user", "content": "q"}], max_tokens=900)
    assert client.last_rate_limit == {"x-ratelimit-remaining-requests": "974"}


def test_a_client_without_with_raw_response_still_works() -> None:
    """The stand-ins above mostly lack it, and that must not be a failure."""
    client = groq([said("ok [C1].")])
    assert text_of(client.chat(messages=[{"role": "user", "content": "q"}])) == "ok [C1]."
    assert client.last_rate_limit == {}


# --- translation, on its own ----------------------------------------------------


def test_tools_are_translated_field_by_field() -> None:
    converted = to_openai_tools(
        [{"name": "get_zones", "description": "zones at a point", "input_schema": {"type": "object"}}]
    )
    assert converted == [
        {
            "type": "function",
            "function": {
                "name": "get_zones",
                "description": "zones at a point",
                "parameters": {"type": "object"},
            },
        }
    ]
    assert to_openai_tools(None) == []


def test_an_assistant_turn_with_text_and_a_tool_call_keeps_both() -> None:
    converted = to_openai_messages(
        [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me look that up."},
                    {"type": "tool_use", "id": "t1", "name": "get_zones", "input": {"lat": 28.6}},
                ],
            }
        ]
    )
    assert converted[0]["content"] == "Let me look that up."
    assert converted[0]["tool_calls"][0]["function"]["name"] == "get_zones"


def test_several_tool_results_become_several_tool_messages() -> None:
    """A model may ask for two tools in one turn, and each result needs its own id."""
    converted = to_openai_messages(
        [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": "{}"},
                    {"type": "tool_result", "tool_use_id": "t2", "content": "{}"},
                ],
            }
        ]
    )
    assert [turn["tool_call_id"] for turn in converted] == ["t1", "t2"]
    assert all(turn["role"] == "tool" for turn in converted)


def test_a_tool_result_given_as_blocks_is_flattened_to_text() -> None:
    converted = to_openai_messages(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": [{"type": "text", "text": "found it"}],
                    }
                ],
            }
        ]
    )
    assert converted[0]["content"] == "found it"


def test_the_retry_turn_answer_py_builds_is_translated() -> None:
    """`answer.py` appends its own answer as a plain string, then the problems."""
    converted = to_openai_messages(
        [
            {"role": "user", "content": "Sources:\n\n[C1] ..."},
            {"role": "assistant", "content": "An uncited sentence."},
            {"role": "user", "content": "Your previous answer failed the citation check."},
        ],
        system="the rules",
    )
    assert [turn["role"] for turn in converted] == ["system", "user", "assistant", "user"]
    assert converted[2]["content"] == "An uncited sentence."


def test_a_completion_with_no_choices_is_an_empty_response() -> None:
    assert from_openai_response(FakeCompletion(choices=[]), GPT_OSS).content == []


def test_a_truncated_completion_says_so() -> None:
    """`length` is OpenAI's word for Anthropic's `max_tokens`."""
    completion = FakeCompletion(
        choices=[FakeChoice(message=FakeMessage(content="half an ans"), finish_reason="length")]
    )
    assert from_openai_response(completion, GPT_OSS).stop_reason == "max_tokens"


# --- choosing the client --------------------------------------------------------


def test_get_llm_builds_the_groq_client_when_the_provider_says_so(monkeypatch) -> None:
    """Checked without a key, by watching which class `get_llm` reaches for."""
    built: list[str] = []
    monkeypatch.setattr(llm_module, "GroqLLM", lambda: built.append("groq") or "groq-client")
    monkeypatch.setattr(
        llm_module, "AnthropicLLM", lambda: built.append("anthropic") or "anthropic-client"
    )
    assert get_llm(provider="groq") == "groq-client"
    assert get_llm(provider="anthropic") == "anthropic-client"
    assert built == ["groq", "anthropic"]


def test_the_fake_client_still_wins_over_any_provider(monkeypatch) -> None:
    """A test must never reach a real API, whatever `LLM_PROVIDER` says (D-040)."""
    monkeypatch.setattr(
        llm_module, "GroqLLM", lambda: pytest.fail("get_llm(fake=True) built a real client")
    )
    client = get_llm(fake=True, responses=["hello [C1]."])
    assert client.chat(messages=[{"role": "user", "content": "q"}]) is not None


# --- a final answer sent as a tool call Groq refused (D-100) --------------------


ANSWER_AS_A_TOOL_CALL = json.dumps(
    {
        "name": "JSON",
        "arguments": {
            "abstain": None,
            "sentences": [{"text": "Ground coverage is 40%.", "citations": ["S1"]}],
        },
    }
)


def test_a_rejected_call_to_a_tool_we_never_offered_is_read_as_the_answer(clock) -> None:
    """Phase A's agent 500: the answer was written, paid for, and thrown away."""
    client = groq([tool_use_failed(ANSWER_AS_A_TOOL_CALL)])
    response = client.chat(
        messages=[{"role": "user", "content": "what can I build?"}],
        tools=AGENT_TOOLS,
    )

    assert json.loads(text_of(response)) == {
        "abstain": None,
        "sentences": [{"text": "Ground coverage is 40%.", "citations": ["S1"]}],
    }
    assert tool_calls_of(response) == [], "a rescued answer is a final answer"
    assert client.tool_call_rescues == 1


def test_a_rejected_call_to_a_real_tool_is_not_rescued(clock) -> None:
    """A refused `search_clauses` is a different fault, and guessing at it would
    invent a tool result nobody ran."""
    rejected = json.dumps(
        {"name": "search_clauses", "arguments": {"sentences": [], "abstain": "no"}}
    )
    client = groq([tool_use_failed(rejected)])
    with pytest.raises(FakeAPIError):
        client.chat(messages=[{"role": "user", "content": "hi"}], tools=AGENT_TOOLS)


def test_a_rejected_generation_that_is_not_an_answer_is_not_rescued(clock) -> None:
    """Only an answer object is rescuable. Anything else stays a failed request."""
    client = groq([tool_use_failed(json.dumps({"name": "JSON", "arguments": {"q": 1}}))])
    with pytest.raises(FakeAPIError):
        client.chat(messages=[{"role": "user", "content": "hi"}], tools=AGENT_TOOLS)


def test_an_unparseable_rejected_generation_is_not_rescued(clock) -> None:
    client = groq([tool_use_failed("{not json at all")])
    with pytest.raises(FakeAPIError):
        client.chat(messages=[{"role": "user", "content": "hi"}], tools=AGENT_TOOLS)


def test_a_400_that_is_not_tool_use_failed_is_not_rescued(clock) -> None:
    """The rescue is keyed on Groq's own code, not on "a 400 happened"."""
    error = FakeAPIError("Error code: 400 - bad request", 400)
    client = groq([error])
    with pytest.raises(FakeAPIError):
        client.chat(messages=[{"role": "user", "content": "hi"}], tools=AGENT_TOOLS)


def test_salvaged_answer_reads_arguments_sent_as_a_json_string() -> None:
    """Some replies nest the arguments as text, which is how OpenAI tool calls work."""
    rejected = json.dumps({"name": "JSON", "arguments": json.dumps({"abstain": "no"})})
    assert salvaged_answer(tool_use_failed(rejected), ["search_clauses"]) == '{"abstain": "no"}'


def test_offered_tool_names_reads_the_payload_the_sdk_was_sent() -> None:
    payload = {"tools": to_openai_tools(AGENT_TOOLS)}
    assert offered_tool_names(payload) == list(TOOL_NAMES)
    assert offered_tool_names({}) == []


def test_is_provider_error_tells_an_sdk_failure_from_one_of_ours() -> None:
    """What `app/api.py` answers with a 503 rather than letting it become a 500."""
    import httpx
    import openai

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request, json={})
    assert is_provider_error(openai.RateLimitError("busy", response=response, body=None))
    assert is_provider_error(openai.APITimeoutError(request=request))
    assert is_provider_error(openai.APIConnectionError(request=request))
    assert not is_provider_error(ValueError("our own bug"))
    assert not is_provider_error(FakeAPIError("not from an sdk", 429))


def test_provider_error_line_is_one_line_and_names_the_type() -> None:
    multiline = "two" + chr(10) + "lines"
    line = provider_error_line(FakeAPIError(multiline, 500))
    assert line == "FakeAPIError: two lines"
    assert len(provider_error_line(FakeAPIError("x" * 900, 500))) < 320
