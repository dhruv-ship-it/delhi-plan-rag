"""The single door to the Anthropic API. Every LLM call in ZoneWise goes through ask()."""

import anthropic

from app.config import settings

MISSING_KEY_MESSAGE = (
    "No Anthropic API key found. ZoneWise needs one from Day 4 onwards.\n"
    "To add it:\n"
    "  1. Copy .env.example to .env\n"
    "  2. Put your key in .env as ANTHROPIC_API_KEY=sk-ant-...\n"
    "  3. Run the command again (.env is read automatically and is never committed)."
)


def ask(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 300,
    temperature: float = 0.0,
) -> str:
    """Send one prompt to Claude and return the reply as plain text."""
    if not settings.anthropic_api_key:
        raise RuntimeError(MISSING_KEY_MESSAGE)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    extra = {"system": system} if system is not None else {}
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
        **extra,
    )
    return "".join(block.text for block in response.content if block.type == "text")


if __name__ == "__main__":
    if not settings.anthropic_api_key:
        print("No ANTHROPIC_API_KEY set, so skipping the test call.")
        print("That is expected before Day 4. See .env.example when you are ready.")
    else:
        print(f"Model: {settings.llm_model}")
        print(ask("Reply with exactly: ZoneWise online"))
