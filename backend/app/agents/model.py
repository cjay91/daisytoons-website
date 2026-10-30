"""Calling the model: the Claude API, or a scripted stand-in for tests and evals."""

import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from functools import lru_cache
from typing import Any, Protocol

from app.config import get_settings

# US dollars per million tokens: input, output, cache read, cache write (5-minute).
PRICES: dict[str, tuple[Decimal, Decimal, Decimal, Decimal]] = {
    "claude-opus-5-5": (Decimal("4"), Decimal("20"), Decimal("0.20"), Decimal("5")),
    "claude-sonnet-5-5": (Decimal("2"), Decimal("10"), Decimal("0.20"), Decimal("2.50")),
    "claude-haiku-5-5": (Decimal("0.10"), Decimal("0.50"), Decimal("0.01"), Decimal("0.125")),
}
# A model missing from the table is costed at the highest price, so limits still hold.
FALLBACK_PRICE = (Decimal("10"), Decimal("50"), Decimal("1"), Decimal("12.50"))
MILLION = Decimal(1_000_000)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


def cost(model: str, usage: Usage) -> Decimal:
    price_in, price_out, price_read, price_write = PRICES.get(model, FALLBACK_PRICE)
    total = (
        usage.input_tokens * price_in
        + usage.output_tokens * price_out
        + usage.cache_read_tokens * price_read
        + usage.cache_write_tokens * price_write
    )
    return (total / MILLION).quantize(Decimal("0.000001"))


@dataclass
class ModelResponse:
    content: list[dict[str, Any]]
    stop_reason: str
    model: str
    usage: Usage
    duration_ms: int = 0


@dataclass
class ModelRequest:
    system: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    effort: str
    max_tokens: int = 16000


# What a model call streams: ("text", str) as text arrives, then ("response", ModelResponse).
ModelEvent = tuple[str, Any]


class Model(Protocol):
    def stream(self, request: ModelRequest) -> Iterator[ModelEvent]: ...


class ClaudeModel:
    """The real model, through the Anthropic SDK.

    Uses adaptive thinking, prompt caching, and the server-side refusal fallback, which retries a
    declined request on another model.
    """

    def __init__(self, model: str | None = None, client: Any = None) -> None:
        self.model = model or get_settings().agent_model
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
        return self._client

    def stream(self, request: ModelRequest) -> Iterator[ModelEvent]:
        started = time.monotonic()
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=request.max_tokens,
            system=request.system,
            messages=request.messages,
            tools=request.tools,
            thinking={"type": "adaptive"},
            output_config={"effort": request.effort},
            cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            for text in stream.text_stream:
                yield ("text", text)
            message = stream.get_final_message()
        usage = message.usage
        yield (
            "response",
            ModelResponse(
                content=[
                    block.model_dump(mode="json", exclude_none=True) for block in message.content
                ],
                stop_reason=message.stop_reason or "end_turn",
                model=message.model,
                usage=Usage(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cache_read_tokens=usage.cache_read_input_tokens or 0,
                    cache_write_tokens=usage.cache_creation_input_tokens or 0,
                ),
                duration_ms=int((time.monotonic() - started) * 1000),
            ),
        )


@lru_cache
def get_model() -> Model:
    return ClaudeModel()


# A scripted turn: the content blocks to answer with, or a function of the request that
# returns them.
Turn = Sequence[dict[str, Any]] | Callable[[ModelRequest], Sequence[dict[str, Any]]]


def text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value}


def tool_use(name: str, tool_input: dict[str, Any], call_id: str | None = None) -> dict[str, Any]:
    return {"type": "tool_use", "id": call_id or f"toolu_{name}", "name": name, "input": tool_input}


@dataclass
class ScriptedModel:
    """Answers with scripted turns, in order, and records each request it was sent."""

    turns: list[Turn]
    model: str = "claude-opus-5-5"
    usage: Usage = field(default_factory=lambda: Usage(input_tokens=1000, output_tokens=100))
    requests: list[ModelRequest] = field(default_factory=list)

    def stream(self, request: ModelRequest) -> Iterator[ModelEvent]:
        # A copy, since the loop goes on adding to the conversation after this call.
        self.requests.append(replace(request, messages=list(request.messages)))
        if not self.turns:
            raise RuntimeError("The scripted model has no turns left.")
        turn = self.turns.pop(0)
        content = [dict(block) for block in (turn(request) if callable(turn) else turn)]
        for block in content:
            if block["type"] == "text":
                yield ("text", block["text"])
        stop = "tool_use" if any(b["type"] == "tool_use" for b in content) else "end_turn"
        yield ("response", ModelResponse(content, stop, self.model, Usage(**vars(self.usage))))
