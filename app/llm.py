"""The single door to the LLM, plus a fake client that stands in for tests.

Every LLM call in ZoneWise goes through this module, so there is exactly one place that
knows the provider, the model name, the API key and the shape of a request.
`app/answer.py` and `app/agent.py` both talk to whatever `get_llm()` hands them and
never import `anthropic` or `openai` themselves.

Three clients implement the same `chat()` method:

  AnthropicLLM   the original: Anthropic's Messages API, needs an `sk-ant-` key
  GroqLLM        Groq's OpenAI-compatible endpoint, needs a `gsk_` key (D-082)
  FakeLLM        returns scripted responses, records what it was asked, costs nothing

`LLM_PROVIDER` in `.env` picks between the two real ones. That split is what lets the
whole answering and agent pipeline be tested — citation validation, retries,
abstention, tool calling — without a key and without a network call. The tests script a
FakeLLM; nothing in `tests/` can reach a real API, because every test passes its own
client in.

**The Anthropic response shape is this project's internal shape.** A response has
`.content` (a list of blocks, each with a `.type`), `.stop_reason` and `.usage`.
`GroqLLM` therefore translates in both directions — the system prompt, the messages,
the tool definitions, the tool calls and the tool results into OpenAI
chat-completions format, and the completion back into blocks — so `answer.py` and
`agent.py` need no provider logic at all. Everything that translation has to know is in
`to_openai_messages`, `to_openai_tools` and `from_openai_response`, each of which is a
plain function a test can call on its own.

**Reasoning text never reaches a user.** `openai/gpt-oss-120b` is a reasoning model and
Groq returns its chain of thought in a separate field on the message.
`from_openai_response` reads `message.content` and nothing else, so the reasoning
cannot reach an answer, a citation or the request log (D-082).
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import (
    PROVIDER_GROQ,
    looks_like_api_key,
    looks_like_groq_key,
    settings,
)

log = logging.getLogger("zonewise.llm")

MISSING_KEY_MESSAGE = (
    "No Anthropic API key found. ZoneWise needs one to produce answers.\n"
    "To add it:\n"
    "  1. Copy .env.example to .env\n"
    "  2. Put your key in .env as ANTHROPIC_API_KEY=sk-ant-...\n"
    "  3. Run the command again (.env is read automatically and is never committed).\n"
    "Search works without a key: try scripts/search.py or POST /api/search."
)

MISSING_GROQ_KEY_MESSAGE = (
    "No usable Groq API key found, and LLM_PROVIDER=groq. ZoneWise needs one to "
    "produce answers.\n"
    "To add it:\n"
    "  1. Copy .env.example to .env\n"
    "  2. Put your key in .env as GROQ_API_KEY=gsk_...\n"
    "  3. Run the command again (.env is read automatically and is never committed).\n"
    "A key must start with 'gsk_' and be at least 40 characters: a placeholder is not "
    "a key, and building a client with one would turn 'no key yet' into a 401 nobody "
    "can interpret (D-082).\n"
    "Search works without a key: try scripts/search.py or POST /api/search."
)


class LLM(Protocol):
    """What `app/answer.py` and `app/agent.py` need from a client.

    `chat` returns an object shaped like an Anthropic Messages response: it has
    `.content` (a list of blocks, each with a `.type`) and `.stop_reason`.
    """

    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Any:
        """Send a conversation and return the raw response."""
        ...


# --- the response shape ---------------------------------------------------------


@dataclass
class TextBlock:
    """A block of text in a response."""

    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    """A tool call in a response."""

    name: str
    input: dict
    id: str = "toolu_fake"
    type: str = "tool_use"


@dataclass
class Usage:
    """What one call cost, in tokens. Named the way Anthropic names it."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Response:
    """A response in this project's internal shape, whoever produced it."""

    content: list[Any]
    stop_reason: str = "end_turn"
    model: str = "fake"
    usage: Usage | None = None


def text_response(text: str) -> Response:
    """A response that is just an answer."""
    return Response(content=[TextBlock(text=text)])


def tool_use_response(name: str, tool_input: dict, call_id: str = "toolu_fake") -> Response:
    """A response that asks for one tool to be run."""
    return Response(
        content=[ToolUseBlock(name=name, input=tool_input, id=call_id)],
        stop_reason="tool_use",
    )


# --- pacing ---------------------------------------------------------------------


class Pacer:
    """Keeps at least `interval` seconds between two calls.

    Written the same way `app/geocode.py`'s limiter is, and for the same reason: the
    lock makes the gap hold when two requests arrive together, which they will once
    the agent runs behind the API. An `interval` of 0 is a no-op, which is the right
    default for a one-question interface; a batch run sets a real gap to stay under a
    provider's requests-per-minute limit (D-082).
    """

    def __init__(self, interval: float) -> None:
        self.interval = max(0.0, float(interval))
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        """Block until it is time to send the next call."""
        if self.interval <= 0:
            return
        with self._lock:
            gap = time.monotonic() - self._last
            if gap < self.interval:
                time.sleep(self.interval - gap)
            self._last = time.monotonic()


#: Shared by every client that does not ask for its own, so two clients in one process
#: still respect one gap between calls.
PACER = Pacer(settings.llm_min_interval_s)


# --- the Anthropic client -------------------------------------------------------


class AnthropicLLM:
    """The real Anthropic client. Needs a key, and every call costs money."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.llm_model
        if not looks_like_api_key(self.api_key):
            raise RuntimeError(MISSING_KEY_MESSAGE)
        self.calls = 0

    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Any:
        """One Messages API call. Returns the response object unchanged."""
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        extra: dict[str, Any] = {}
        if system is not None:
            extra["system"] = system
        if tools:
            extra["tools"] = tools
        self.calls += 1
        PACER.wait()
        return client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
            **extra,
        )


# --- translating to and from OpenAI chat-completions format ---------------------

#: Groq speaks the OpenAI chat-completions API at this address.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

#: What to suggest when the configured model is not one the key can use.
GROQ_FALLBACK_MODEL = "llama-3.3-70b-versatile"

#: How hard a reasoning model should think. "low" because the answering job is short,
#: extractive and bounded by the retrieved clauses — the work that matters is reading
#: six clauses, not planning — and reasoning tokens are billed and rate-limited like
#: any others (D-082).
REASONING_EFFORT = "low"

#: Model ids that take a `reasoning_effort` setting. Matched as a substring because
#: Groq prefixes the open models with their publisher: `openai/gpt-oss-120b`.
REASONING_MODEL_MARKERS = ("gpt-oss",)

#: Extra completion tokens allowed for a reasoning model's hidden thinking.
#:
#: `max_tokens` means different things on the two APIs, and this is the one place that
#: difference has to be absorbed. On Anthropic it bounds the answer. On Groq a
#: reasoning model's chain of thought is counted in the same completion budget, so
#: passing `answer_max_tokens` straight through would let the reasoning eat the answer
#: and truncate it mid-sentence — which the citation check would then reject, turning a
#: provider difference into an abstention. The caller's number keeps its meaning (bound
#: the answer) and the hidden part gets its own headroom (D-082).
REASONING_TOKEN_HEADROOM = 1024

#: OpenAI's finish reasons, in Anthropic's vocabulary.
STOP_REASONS = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "length": "max_tokens",
}

#: The rate-limit headers Groq returns. Logged whenever they are present, so a 429 can
#: be read afterwards rather than guessed at.
RATE_LIMIT_HEADERS = (
    "retry-after",
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-reset-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-tokens",
)

#: How many times a rate-limited call is tried in total, and the first backoff gap.
GROQ_MAX_TRIES = 4
GROQ_BACKOFF_BASE_S = 2.0
GROQ_MAX_BACKOFF_S = 60.0

#: Words that mark an error as "slow down" or "you have run out", rather than as a bug.
QUOTA_MARKERS = (
    "rate limit",
    "rate_limit",
    "ratelimit",
    "too many requests",
    "quota",
    "tokens per day",
    "requests per day",
)


def supports_reasoning_effort(model: str) -> bool:
    """True for a model that takes a `reasoning_effort` setting."""
    name = (model or "").lower()
    return any(marker in name for marker in REASONING_MODEL_MARKERS)


def to_openai_tools(tools: list[dict] | None) -> list[dict]:
    """Our Anthropic-shaped tool definitions as OpenAI function definitions.

    The only differences are the wrapper and the name of the schema field:
    `input_schema` becomes `parameters`.
    """
    converted: list[dict] = []
    for tool in tools or []:
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema") or {"type": "object"},
                },
            }
        )
    return converted


def _result_text(content: Any) -> str:
    """A tool result's content as the one string OpenAI's `tool` role expects."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        if parts:
            return "\n".join(parts)
    return json.dumps(content, ensure_ascii=False)


def to_openai_messages(messages: list[dict], system: str | None = None) -> list[dict]:
    """Our Anthropic-shaped conversation as OpenAI chat-completions messages.

    Four shapes are produced by `answer.py` and `agent.py`, and all four are handled:

      the system prompt                 -> a `system` message in front
      a plain string turn               -> the same turn
      an assistant turn of blocks       -> one assistant message, with `tool_calls` for
                                           the tool_use blocks and the text joined
      a user turn of tool_result blocks -> one `tool` message each, in order

    Order is preserved, which is what makes the tool round trip work: OpenAI requires
    each `tool` message to follow the assistant message whose call it answers, and
    Anthropic's layout — an assistant tool_use turn, then a user turn of tool_results —
    lands in exactly that order when translated turn by turn.
    """
    converted: list[dict] = []
    if system:
        converted.append({"role": "system", "content": system})

    for message in messages:
        role = message.get("role", "user")
        content = message.get("content")

        if isinstance(content, str):
            converted.append({"role": role, "content": content})
            continue
        blocks = [block for block in (content or []) if isinstance(block, dict)]

        if role == "assistant":
            texts = [block.get("text", "") for block in blocks if block.get("type") == "text"]
            tool_calls = [
                {
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                    },
                }
                for block in blocks
                if block.get("type") == "tool_use"
            ]
            turn: dict[str, Any] = {
                "role": "assistant",
                "content": "\n".join(text for text in texts if text.strip()),
            }
            if tool_calls:
                turn["tool_calls"] = tool_calls
            converted.append(turn)
            continue

        spoken: list[str] = []
        for block in blocks:
            if block.get("type") == "tool_result":
                converted.append(
                    {
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": _result_text(block.get("content")),
                    }
                )
            elif block.get("type") == "text":
                spoken.append(block.get("text", ""))
        if spoken:
            converted.append({"role": role, "content": "\n".join(spoken)})

    return converted


def from_openai_response(completion: Any, model: str = "") -> Response:
    """One OpenAI-shaped completion as a `Response` in this project's shape.

    Reads `message.content` and `message.tool_calls`, and **nothing else**. A reasoning
    model's chain of thought arrives in a separate field (`reasoning`), which is never
    looked at, so it cannot reach an answer, a citation or the request log (D-082).
    """
    choices = getattr(completion, "choices", None) or []
    if not choices:
        return Response(content=[], stop_reason="end_turn", model=model, usage=Usage())
    choice = choices[0]
    message = getattr(choice, "message", None)

    blocks: list[Any] = []
    text = (getattr(message, "content", None) or "").strip()
    if text:
        blocks.append(TextBlock(text=text))

    for call in getattr(message, "tool_calls", None) or []:
        function = getattr(call, "function", None)
        try:
            arguments = json.loads(getattr(function, "arguments", None) or "{}")
        except (json.JSONDecodeError, TypeError):
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        blocks.append(
            ToolUseBlock(
                name=getattr(function, "name", "") or "",
                input=arguments,
                id=getattr(call, "id", "") or "",
            )
        )

    finish = getattr(choice, "finish_reason", "") or ""
    stop_reason = STOP_REASONS.get(finish, "end_turn")
    if any(getattr(block, "type", "") == "tool_use" for block in blocks):
        stop_reason = "tool_use"

    raw_usage = getattr(completion, "usage", None)
    usage = Usage(
        input_tokens=int(getattr(raw_usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(raw_usage, "completion_tokens", 0) or 0),
    )
    return Response(
        content=blocks,
        stop_reason=stop_reason,
        model=getattr(completion, "model", None) or model,
        usage=usage,
    )


# --- reading an error -----------------------------------------------------------


def status_of(error: Exception) -> int | None:
    """The HTTP status an SDK error carries, if it carries one."""
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def headers_of(error: Exception) -> dict[str, str]:
    """The response headers an SDK error carries, lower-cased, or an empty dict."""
    raw = getattr(error, "headers", None)
    if raw is None:
        raw = getattr(getattr(error, "response", None), "headers", None)
    if not raw:
        return {}
    try:
        return {str(name).lower(): str(value) for name, value in dict(raw).items()}
    except (TypeError, ValueError):
        return {}


def is_rate_limited(error: Exception) -> bool:
    """True for "slow down" or "you have run out", which are worth retrying.

    A 429 is the normal signal. The text markers catch a free-tier daily quota refusal
    that arrives with a different status, because the right response to both is to wait
    rather than to fail the request straight away.
    """
    if status_of(error) == 429:
        return True
    text = str(error).lower()
    return any(marker in text for marker in QUOTA_MARKERS)


def rejects_reasoning_effort(error: Exception) -> bool:
    """True when the model refused the request *because* of `reasoning_effort`."""
    if status_of(error) not in (400, 404, 422):
        return False
    return "reasoning_effort" in str(error).lower()


def retry_after_of(headers: dict[str, str]) -> float | None:
    """The `retry-after` header in seconds, when there is a usable one."""
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def rate_limit_of(headers: dict[str, str]) -> dict[str, str]:
    """Just the rate-limit headers, for logging and for the run report."""
    return {name: headers[name] for name in RATE_LIMIT_HEADERS if name in headers}


# --- the Groq client ------------------------------------------------------------


class GroqLLM:
    """Groq's OpenAI-compatible chat completions, in the shape ZoneWise reads.

    Built through the `openai` SDK pointed at `GROQ_BASE_URL`, which is Groq's own
    documented way in and means no second HTTP client in this project.

    Refuses to exist without a real-looking key, exactly as `AnthropicLLM` does: a
    placeholder that reads as a key produces a 401 on the first real question, where an
    honest 503 from `/api/ask` tells the user what to do (D-040, D-082).

    `client` is injectable, so the whole translation and retry path is tested against a
    scripted stand-in with no network call. `min_interval_s` gives this client its own
    pacer instead of the shared one, which is what a batch run needs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        client: Any = None,
        min_interval_s: float | None = None,
        max_tries: int = GROQ_MAX_TRIES,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model or settings.llm_model
        if not looks_like_groq_key(self.api_key):
            raise RuntimeError(MISSING_GROQ_KEY_MESSAGE)
        self.provider = PROVIDER_GROQ
        self.max_tries = max(1, int(max_tries))
        self.pacer = PACER if min_interval_s is None else Pacer(min_interval_s)
        self.reasoning_effort = (
            REASONING_EFFORT if supports_reasoning_effort(self.model) else None
        )
        #: Counters, read by scripts/live_run.py for its report.
        self.calls = 0
        self.retries = 0
        self.rate_limit_events = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.last_rate_limit: dict[str, str] = {}
        self._client = client

    @property
    def client(self) -> Any:
        """The `openai` client, built once, pointed at Groq."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key, base_url=GROQ_BASE_URL)
        return self._client

    def list_models(self) -> list[str]:
        """Every model id this key may use, sorted. Empty when the listing failed."""
        try:
            listing = self.client.models.list()
        except Exception as exc:
            log.warning("groq model listing failed: %s", exc)
            return []
        return sorted(
            str(getattr(item, "id", "")) for item in (getattr(listing, "data", None) or [])
        )

    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Any:
        """One chat-completions call, translated both ways.

        `max_tokens` bounds the **answer**; a reasoning model gets
        `REASONING_TOKEN_HEADROOM` more for its hidden thinking, which Groq counts in
        the same completion budget.
        """
        budget = max_tokens + (REASONING_TOKEN_HEADROOM if self.reasoning_effort else 0)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": to_openai_messages(messages, system),
            "max_tokens": budget,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = to_openai_tools(tools)
            payload["tool_choice"] = "auto"
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        return self._send(payload)

    def _send(self, payload: dict) -> Response:
        """Send one payload, dropping `reasoning_effort` if the model refuses it."""
        try:
            return self._send_with_retries(payload)
        except Exception as exc:
            if "reasoning_effort" in payload and rejects_reasoning_effort(exc):
                log.warning(
                    "%s does not accept reasoning_effort=%s; sending without it",
                    self.model,
                    payload["reasoning_effort"],
                )
                self.reasoning_effort = None
                payload.pop("reasoning_effort")
                return self._send_with_retries(payload)
            raise

    def _send_with_retries(self, payload: dict) -> Response:
        """Send one payload, backing off exponentially while it is rate-limited.

        Up to `max_tries` attempts. `retry-after` is honoured when Groq sends one,
        because the service knows when its own window resets better than a doubling
        guess does; otherwise the gap doubles from `GROQ_BACKOFF_BASE_S`.
        """
        delay = GROQ_BACKOFF_BASE_S

        for attempt in range(1, self.max_tries + 1):
            self.pacer.wait()
            try:
                completion, headers = self._create(payload)
            except Exception as exc:
                headers = headers_of(exc)
                limits = rate_limit_of(headers)
                if limits:
                    self.last_rate_limit = limits
                if not is_rate_limited(exc):
                    raise
                self.rate_limit_events += 1
                log.warning(
                    "groq rate limited on attempt %d of %d: %s | %s",
                    attempt,
                    self.max_tries,
                    exc,
                    limits or "no rate-limit headers",
                )
                if attempt == self.max_tries:
                    raise
                self.retries += 1
                wait = retry_after_of(headers)
                if wait is None:
                    wait = min(delay, GROQ_MAX_BACKOFF_S)
                    delay *= 2
                log.warning("waiting %.1fs before retrying", wait)
                time.sleep(wait)
                continue

            self.calls += 1
            limits = rate_limit_of(headers)
            if limits:
                self.last_rate_limit = limits
                log.debug("groq rate limits: %s", limits)
            response = from_openai_response(completion, self.model)
            if response.usage is not None:
                self.input_tokens += response.usage.input_tokens
                self.output_tokens += response.usage.output_tokens
            return response

        raise RuntimeError("no attempt was made")  # unreachable: the loop always returns

    def _create(self, payload: dict) -> tuple[Any, dict[str, str]]:
        """One raw call. Returns the completion and the response headers.

        `with_raw_response` is how the `openai` SDK hands back headers, and the
        rate-limit headers are the only way to see how much of a free tier is left. A
        client that does not offer it — a stand-in in a test — still works, with no
        headers.
        """
        endpoint = self.client.chat.completions
        raw = getattr(endpoint, "with_raw_response", None)
        if raw is None:
            return endpoint.create(**payload), {}

        wrapped = raw.create(**payload)
        try:
            headers = {
                str(name).lower(): str(value)
                for name, value in dict(getattr(wrapped, "headers", {}) or {}).items()
            }
        except (TypeError, ValueError):
            headers = {}
        return wrapped.parse(), headers


# --- the fake client -----------------------------------------------------------


class ScriptExhausted(RuntimeError):
    """Raised when a FakeLLM is asked for more responses than it was given.

    This is deliberately an error rather than a default reply: a test that makes an
    unexpected extra call has found a real bug, and a silent fallback would hide it.
    """


@dataclass
class FakeLLM:
    """A scripted stand-in for a real client, used by every test.

    `responses` are handed out in order. Each may be a `Response`, a plain string
    (wrapped as text), or a callable taking the keyword arguments of the call, for a
    test that needs to look at the prompt before deciding what to reply.

    Everything the client was asked is kept in `calls`, so a test can assert on the
    prompt it built as well as on the answer it got back.
    """

    responses: list[Any] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    model: str = "fake"

    def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> Any:
        """Record the call and return the next scripted response."""
        call = {
            "messages": messages,
            "system": system,
            "tools": tools,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        self.calls.append(call)
        if len(self.calls) > len(self.responses):
            raise ScriptExhausted(
                f"FakeLLM was called {len(self.calls)} time(s) but only "
                f"{len(self.responses)} response(s) were scripted"
            )
        reply = self.responses[len(self.calls) - 1]
        if callable(reply):
            reply = reply(**call)
        if isinstance(reply, str):
            reply = text_response(reply)
        return reply

    @property
    def call_count(self) -> int:
        """How many times the client was asked for a response."""
        return len(self.calls)

    def last_prompt(self) -> str:
        """The text of the most recent user message, for assertions in tests."""
        if not self.calls:
            return ""
        content = self.calls[-1]["messages"][-1]["content"]
        if isinstance(content, str):
            return content
        return "\n".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )


# --- choosing one --------------------------------------------------------------


def get_llm(
    fake: bool | None = None,
    responses: list[Any] | None = None,
    provider: str | None = None,
) -> LLM:
    """The client to use.

    `fake=True`, or `settings.use_fake_llm`, gives a FakeLLM; anything else gives the
    real client for `settings.llm_provider`, which raises if there is no key rather
    than quietly faking an answer. A caller that wanted a real answer and got a
    made-up one would be far worse than an error (see D-040).
    """
    if fake or settings.use_fake_llm:
        return FakeLLM(responses=list(responses or []))
    if (provider or settings.llm_provider) == PROVIDER_GROQ:
        return GroqLLM()
    return AnthropicLLM()


def text_of(response: Any) -> str:
    """All the text blocks of a response, joined. Tool-use blocks are ignored."""
    return "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )


def tool_calls_of(response: Any) -> list[Any]:
    """The tool-use blocks of a response, in order."""
    return [block for block in response.content if getattr(block, "type", "") == "tool_use"]


def usage_of(response: Any) -> tuple[int, int]:
    """(input tokens, output tokens) for one response, 0 when it does not say.

    Both providers name these fields the same way on the internal shape, so a caller
    recording what a run cost needs no provider logic.
    """
    usage = getattr(response, "usage", None)
    return (
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
    )


def ask(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 300,
    temperature: float = 0.0,
    llm: LLM | None = None,
) -> str:
    """Send one prompt and return the reply as plain text.

    The simple door, kept from Day 1 and now built on `chat`, so there is still one
    place that talks to the API.
    """
    client = llm or get_llm()
    response = client.chat(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return text_of(response)


# --- the self-check: uv run python -m app.llm -----------------------------------

PING_PROMPT = "Reply with exactly: ZoneWise online"

#: One trivial tool, so the round trip is confirmed without involving the real ones.
PING_TOOL = [
    {
        "name": "zonewise_ping",
        "description": "Confirm that tool calling works. Call it once with ok=true.",
        "input_schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean", "description": "Always true."}},
            "required": ["ok"],
        },
    }
]
PING_TOOL_PROMPT = (
    "Call the zonewise_ping tool once with ok set to true. Do not reply with text."
)


def check_groq() -> int:
    """List the models, send two pings, and say whether Groq is usable. 0 when it is."""
    try:
        client = GroqLLM()
    except RuntimeError as exc:
        print(exc)
        return 1

    print("provider: groq")
    print(f"model:    {client.model}")
    print(f"effort:   reasoning_effort={client.reasoning_effort or 'not sent'}")
    print()

    names = client.list_models()
    if not names:
        print("Could not list the models for this key; carrying on to the ping.")
    else:
        print(f"{len(names)} model(s) available to this key.")
        if client.model in names:
            print(f"  {client.model} is among them.")
        else:
            print(f"  WARNING: {client.model} is NOT among them, so LLM_MODEL is wrong.")
            if GROQ_FALLBACK_MODEL in names:
                print(f"  {GROQ_FALLBACK_MODEL} is listed: try LLM_MODEL={GROQ_FALLBACK_MODEL}")
            else:
                sample = ", ".join(names[:10])
                print(f"  Pick one of: {sample}{' ...' if len(names) > 10 else ''}")
            return 1
    print()

    try:
        reply = client.chat(
            messages=[{"role": "user", "content": PING_PROMPT}],
            max_tokens=64,
        )
    except Exception as exc:
        print(f"The plain ping failed: {type(exc).__name__}: {exc}")
        return 1
    plain = text_of(reply).strip()
    sent, received = usage_of(reply)
    print(f"plain ping -> {plain!r}  ({sent} in, {received} out)")

    try:
        tooled = client.chat(
            messages=[{"role": "user", "content": PING_TOOL_PROMPT}],
            tools=PING_TOOL,
            max_tokens=256,
        )
    except Exception as exc:
        print(f"The tool ping failed: {type(exc).__name__}: {exc}")
        return 1
    requested = tool_calls_of(tooled)
    sent, received = usage_of(tooled)
    print(
        f"tool ping  -> {[block.name for block in requested] or 'no tool call'}  "
        f"({sent} in, {received} out)"
    )
    if client.last_rate_limit:
        print(f"rate limits: {client.last_rate_limit}")
    print()

    if not plain:
        print("The model returned no text, so something is wrong with the translation.")
        return 1
    if not requested:
        print(f"ZoneWise online (groq/{client.model}, but TOOLS FAILED: no tool call made)")
        return 1
    print(f"ZoneWise online (groq/{client.model}, tools OK)")
    return 0


def check_anthropic() -> int:
    """The original check: one prompt, if there is a key. 0 when it worked."""
    if not settings.has_api_key:
        print("No usable ANTHROPIC_API_KEY set, so skipping the test call.")
        print("See .env.example when you are ready.")
        print('Search needs no key: uv run python scripts/search.py "TOD plot size"')
        return 0
    print(f"Model: {settings.llm_model}")
    try:
        print(ask(PING_PROMPT))
    except Exception as exc:
        print(f"The ping failed: {type(exc).__name__}: {exc}")
        return 1
    print(f"ZoneWise online (anthropic/{settings.llm_model})")
    return 0


def main() -> int:
    """Check whichever provider is configured."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if settings.llm_provider == PROVIDER_GROQ:
        return check_groq()
    return check_anthropic()


if __name__ == "__main__":
    raise SystemExit(main())
