"""The single door to the Anthropic API, plus a fake client that stands in for tests.

Every LLM call in ZoneWise goes through this module, so there is exactly one place that
knows the model name, the API key and the shape of a request. `app/answer.py` and
`app/agent.py` both talk to whatever `get_llm()` hands them and never import `anthropic`
themselves.

Two clients implement the same two methods:

  AnthropicLLM   the real thing, which costs money and needs a key
  FakeLLM        returns scripted responses, records what it was asked, costs nothing

That split is what lets the whole answering and agent pipeline be tested — citation
validation, retries, abstention, tool calling — without a key and without a network
call. The tests script a FakeLLM; nothing in `tests/` can reach the real API, because
every test passes its own client in.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import looks_like_api_key, settings

MISSING_KEY_MESSAGE = (
    "No Anthropic API key found. ZoneWise needs one to produce answers.\n"
    "To add it:\n"
    "  1. Copy .env.example to .env\n"
    "  2. Put your key in .env as ANTHROPIC_API_KEY=sk-ant-...\n"
    "  3. Run the command again (.env is read automatically and is never committed).\n"
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


# --- the real client -----------------------------------------------------------


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
        return client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
            **extra,
        )


# --- the fake client -----------------------------------------------------------


@dataclass
class FakeTextBlock:
    """A block of text in a fake response."""

    text: str
    type: str = "text"


@dataclass
class FakeToolUseBlock:
    """A tool call in a fake response."""

    name: str
    input: dict
    id: str = "toolu_fake"
    type: str = "tool_use"


@dataclass
class FakeResponse:
    """What FakeLLM.chat returns: the same shape the real response has."""

    content: list[Any]
    stop_reason: str = "end_turn"
    model: str = "fake"


def text_response(text: str) -> FakeResponse:
    """A fake response that is just an answer."""
    return FakeResponse(content=[FakeTextBlock(text=text)])


def tool_use_response(name: str, tool_input: dict, call_id: str = "toolu_fake") -> FakeResponse:
    """A fake response that asks for one tool to be run."""
    return FakeResponse(
        content=[FakeToolUseBlock(name=name, input=tool_input, id=call_id)],
        stop_reason="tool_use",
    )


class ScriptExhausted(RuntimeError):
    """Raised when a FakeLLM is asked for more responses than it was given.

    This is deliberately an error rather than a default reply: a test that makes an
    unexpected extra call has found a real bug, and a silent fallback would hide it.
    """


@dataclass
class FakeLLM:
    """A scripted stand-in for the real client, used by every test.

    `responses` are handed out in order. Each may be a `FakeResponse`, a plain string
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


def get_llm(fake: bool | None = None, responses: list[Any] | None = None) -> LLM:
    """The client to use.

    `fake=True`, or `settings.use_fake_llm`, gives a FakeLLM; anything else gives the
    real client, which raises if there is no key rather than quietly faking an answer.
    A caller that wanted a real answer and got a made-up one would be far worse than an
    error (see D-040).
    """
    if fake or settings.use_fake_llm:
        return FakeLLM(responses=list(responses or []))
    return AnthropicLLM()


def text_of(response: Any) -> str:
    """All the text blocks of a response, joined. Tool-use blocks are ignored."""
    return "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )


def tool_calls_of(response: Any) -> list[Any]:
    """The tool-use blocks of a response, in order."""
    return [block for block in response.content if getattr(block, "type", "") == "tool_use"]


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


if __name__ == "__main__":
    if not settings.has_api_key:
        print("No usable ANTHROPIC_API_KEY set, so skipping the test call.")
        print("That is expected before Day 4. See .env.example when you are ready.")
        print("Search needs no key: uv run python scripts/search.py \"TOD plot size\"")
    else:
        print(f"Model: {settings.llm_model}")
        print(ask("Reply with exactly: ZoneWise online"))
