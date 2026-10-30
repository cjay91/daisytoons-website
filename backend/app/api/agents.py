"""The storefront's agents: a streaming chat, and suggestions for gift messages.

The chat answers with server-sent events, one JSON object per `data:` line:
  {"type": "start", "conversation_id": "..."}   first, so the next message can carry it on
  {"type": "text", "text": "..."}               the reply, a piece at a time
  {"type": "tool", "tool": "add_to_cart", "ok": true}   after each tool call
  {"type": "done", "status": "finished", "text": "..."} last
"""

import json
import re
import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agents.context import Actor
from app.agents.core import run, run_stream
from app.agents.customer_agents import CUSTOMER_AGENTS, GIFT_MESSAGE
from app.agents.customer_tools import contact_options
from app.agents.model import Model, get_model
from app.api.deps import DB, CartToken, ClientIP, CurrentStaff, OptionalCustomer, RateCounter
from app.config import get_settings
from app.errors import AppError
from app.models import ActorKind, AgentRun, RunStatus
from app.ratelimit import CHAT_PER_IP, GIFT_MESSAGE_PER_IP, check
from app.schemas import (
    AgentRunListOut,
    AgentStatusOut,
    ChatRequest,
    ContactOut,
    ConversationOut,
    GiftMessageOut,
    GiftMessageRequest,
)
from app.services import agent_runs
from app.services.agent_runs import customer_spend_today

router = APIRouter(prefix="/agents", tags=["agents"])

MAX_MESSAGE_LENGTH = 300  # what fits on the gift card (Order.gift_message)


class AgentsUnavailable(AppError):
    status_code = 503
    code = "agents_unavailable"


def get_agent_model() -> Model | None:
    """The real model, or None when no Anthropic key is set and the agents are off."""
    return get_model() if get_settings().anthropic_api_key else None


AgentModel = Annotated[Model | None, Depends(get_agent_model)]


def _available(db: DB, model: Model | None) -> Model:
    if model is None:
        raise AgentsUnavailable("The shop assistant isn't available. Please email us instead.")
    if customer_spend_today(db) >= get_settings().customer_agents_daily_budget:
        raise AgentsUnavailable("The shop assistant is resting for today. Please email us.")
    return model


def _owned_conversation(db: DB, actor: Actor, agent: str, conversation_id: str | None) -> str:
    """The conversation to carry on, or a new one if it isn't this visitor's with this agent."""
    if conversation_id:
        last = db.scalar(
            select(AgentRun)
            .where(AgentRun.conversation_id == conversation_id)
            .order_by(AgentRun.id.desc())
            .limit(1)
        )
        if (
            last is not None
            and last.agent == agent
            and last.actor_kind == ActorKind.CUSTOMER
            and last.customer_id == actor.customer_id
        ):
            return conversation_id
    return str(uuid.uuid4())


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


@router.get("/status")
def agent_status(db: DB, model: AgentModel) -> AgentStatusOut:
    """Whether the storefront should show the chat, and how to reach a person either way."""
    try:
        _available(db, model)
        enabled = True
    except AgentsUnavailable:
        enabled = False
    return AgentStatusOut(enabled=enabled, contact=ContactOut(**contact_options()))


@router.post("/chat")
def chat(
    db: DB,
    counter: RateCounter,
    ip: ClientIP,
    body: ChatRequest,
    customer: OptionalCustomer,
    model: AgentModel,
    token: CartToken = None,
) -> StreamingResponse:
    check(counter, CHAT_PER_IP, ip)
    model = _available(db, model)
    agent = CUSTOMER_AGENTS[body.agent]
    actor = Actor.for_customer(customer, token)
    conversation_id = _owned_conversation(db, actor, agent.name, body.conversation_id)

    def events() -> Iterator[str]:
        yield _sse({"type": "start", "conversation_id": conversation_id})
        for event in run_stream(db, agent, actor, body.message, model, conversation_id):
            if event.type == "text":
                yield _sse({"type": "text", "text": event.data["text"]})
            elif event.type == "tool_finished":
                yield _sse({"type": "tool", "tool": event.data["tool"], "ok": event.data["ok"]})
            elif event.type == "done":
                done = {"type": "done", "status": event.data["status"], "text": event.data["text"]}
                yield _sse(done)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def parse_suggestions(text: str) -> list[str]:
    """The model's "- " lines, cleaned up and cut to what fits on the card."""
    suggestions = []
    for line in text.splitlines():
        match = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.+)$", line)
        if not match:
            continue
        message = match.group(1).strip().strip('"“”').strip()
        if message and len(message) <= MAX_MESSAGE_LENGTH:
            suggestions.append(message)
    return suggestions[:3]


@router.post("/gift-message")
def suggest_gift_messages(
    db: DB,
    counter: RateCounter,
    ip: ClientIP,
    body: GiftMessageRequest,
    customer: OptionalCustomer,
    model: AgentModel,
) -> GiftMessageOut:
    check(counter, GIFT_MESSAGE_PER_IP, ip)
    model = _available(db, model)
    brief = "\n".join(
        f"{label}: {value.strip()}"
        for label, value in [
            ("Occasion", body.occasion),
            ("For", body.recipient),
            ("Tone", body.tone),
            ("Details", body.details),
        ]
        if value.strip()
    )
    result = run(db, GIFT_MESSAGE, Actor.for_customer(customer), brief or "A gift.", model)
    suggestions = parse_suggestions(result.text)
    if result.run.status != RunStatus.FINISHED or not suggestions:
        raise AgentsUnavailable("Couldn't write suggestions just now. Please try again.")
    return GiftMessageOut(suggestions=suggestions)


# Tracing, for the console

staff_router = APIRouter(prefix="/staff", tags=["staff agents"])


@staff_router.get("/agent-runs")
def list_agent_runs(
    db: DB,
    staff: CurrentStaff,
    agent: str | None = None,
    status: RunStatus | None = None,
    before: int | None = None,
) -> AgentRunListOut:
    """The latest runs, newest first, with token and cost totals."""
    return agent_runs.list_runs(db, staff, agent, status, before)


@staff_router.get("/agent-runs/{run_id}")
def get_agent_conversation(db: DB, staff: CurrentStaff, run_id: int) -> ConversationOut:
    """The conversation a run belongs to, with every message and tool call in it."""
    return agent_runs.get_conversation(db, staff, run_id)
