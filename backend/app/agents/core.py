"""The agent loop: call the model, run the tools it asks for, repeat until it answers.

Every model call and tool call is recorded as it happens, so a run can be traced and its
conversation carried on later. A run stops at its step, token or cost limit, whatever the model
wants.
"""

import json
import logging
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.context import Actor
from app.agents.model import Model, ModelRequest, ModelResponse, cost
from app.agents.tools import Tool, ToolContext, registry
from app.errors import AppError
from app.models import (
    AgentMessage,
    AgentRun,
    AgentToolCall,
    ApprovalRequest,
    ApprovalStatus,
    AuditEntry,
    Risk,
    RunStatus,
)

logger = logging.getLogger(__name__)

APPROVAL_LIFETIME = timedelta(days=7)
LIMIT_REPLY = (
    "Sorry, I couldn't finish that. I've passed it to the team, and someone will follow up."
)
FAILURE_REPLY = "Sorry, something went wrong on our side. Please try again in a moment."


@dataclass(frozen=True)
class Limits:
    steps: int = 10  # model calls per run
    tokens: int = 50_000
    cost: Decimal = Decimal("0.50")  # US dollars


@dataclass(frozen=True)
class Agent:
    name: str
    system: str
    tools: list[str]
    effort: str = "medium"
    limits: Limits = field(default_factory=Limits)

    def tools_for(self, actor: Actor) -> list[Tool]:
        tools = [registry.get(name) for name in self.tools]
        return [tool for tool in tools if tool is not None and tool.offered_to(actor)]


@dataclass
class Event:
    """What a streaming run reports: text, tool_started, tool_finished, approval, done."""

    type: str
    data: dict[str, Any]


@dataclass
class RunResult:
    run: AgentRun
    text: str
    events: list[Event]


def _blocks_text(content: list[dict[str, Any]]) -> str:
    return "".join(block["text"] for block in content if block.get("type") == "text").strip()


def _unanswered(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Error results for tool calls a failed run never answered, so the history stays valid."""
    if message["role"] != "assistant":
        return []
    return [
        {"type": "tool_result", "tool_use_id": b["id"], "content": "Not run.", "is_error": True}
        for b in message["content"]
        if b.get("type") == "tool_use"
    ]


def _history(db: Session, conversation_id: str) -> list[dict[str, Any]]:
    """The conversation so far, with back-to-back user messages merged, as the API expects."""
    rows = db.scalars(
        select(AgentMessage)
        .join(AgentRun)
        .where(AgentRun.conversation_id == conversation_id)
        .order_by(AgentMessage.id)
    )
    messages: list[dict[str, Any]] = []
    for row in rows:
        content = list(row.content)
        if messages and row.role == "user" and messages[-1]["role"] == "assistant":
            answered = {b.get("tool_use_id") for b in content}
            missing = [r for r in _unanswered(messages[-1]) if r["tool_use_id"] not in answered]
            content = [*missing, *content]
        elif messages and row.role == "assistant" and messages[-1]["role"] == "assistant":
            messages.append({"role": "user", "content": _unanswered(messages[-1])})
        if messages and messages[-1]["role"] == row.role == "user":
            messages[-1]["content"] = [*messages[-1]["content"], *content]
        else:
            messages.append({"role": row.role, "content": content})
    if messages and (missing := _unanswered(messages[-1])):
        messages.append({"role": "user", "content": missing})
    return messages


def _limit_reached(agent: Agent, run: AgentRun) -> str | None:
    if run.steps >= agent.limits.steps:
        return f"step limit ({agent.limits.steps})"
    if run.input_tokens + run.output_tokens >= agent.limits.tokens:
        return f"token limit ({agent.limits.tokens})"
    if run.cost >= agent.limits.cost:
        return f"cost limit (${agent.limits.cost})"
    return None


def _record_response(db: Session, run: AgentRun, response: ModelResponse) -> None:
    price = cost(response.model, response.usage)
    usage = response.usage
    db.add(
        AgentMessage(
            run=run,
            role="assistant",
            content=response.content,
            model=response.model,
            stop_reason=response.stop_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            cost=price,
            duration_ms=response.duration_ms,
        )
    )
    run.steps += 1
    run.input_tokens += usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens
    run.output_tokens += usage.output_tokens
    run.cost += price


def execute(ctx: ToolContext, tool: Tool, data: Any) -> Any:
    """Run a tool as `ctx.actor`, after checking its permission, and audit it if it writes."""
    if not ctx.actor.allows(tool.permission):
        raise PermissionError(f"Not allowed to use {tool.name}.")
    return tool.run(ctx, data)


def audit(
    db: Session,
    run: AgentRun,
    tool: Tool,
    tool_input: dict[str, Any],
    result: Any,
    approval: ApprovalRequest | None = None,
) -> None:
    db.add(
        AuditEntry(
            run_id=run.id,
            agent=run.agent,
            tool=tool.name,
            input=tool_input,
            result=result,
            actor_kind=run.actor_kind,
            customer_id=run.customer_id,
            staff_id=run.staff_id,
            approval_id=approval.id if approval else None,
            approved_by_id=approval.decided_by_id if approval else None,
        )
    )


def _call_tool(
    db: Session, agent: Agent, actor: Actor, run: AgentRun, block: dict[str, Any], reason: str
) -> tuple[dict[str, Any], Event]:
    """Run one tool_use block and return its tool_result block and an event for the stream."""
    started = time.monotonic()
    call = AgentToolCall(
        run=run, tool_use_id=block["id"], tool=block["name"], input=block.get("input") or {}
    )
    db.add(call)
    tool = registry.get(block["name"])
    output: Any = None
    error: str | None = None
    approval: ApprovalRequest | None = None

    if tool is None or block["name"] not in agent.tools or not tool.offered_to(actor):
        error = f"There is no tool called {block['name']} available to you."
    else:
        call.risk = tool.risk
        try:
            data = tool.input_model.model_validate(call.input)
            if tool.risk == Risk.APPROVE:
                db.flush()
                approval = ApprovalRequest(
                    run_id=run.id,
                    tool_call_id=call.id,
                    tool=tool.name,
                    input=data.model_dump(mode="json"),
                    reason=reason,
                    status=ApprovalStatus.PENDING,
                    expires_at=datetime.now(UTC) + APPROVAL_LIFETIME,
                )
                db.add(approval)
                db.flush()
                output = {
                    "status": "waiting_for_approval",
                    "approval_request": approval.id,
                    "message": "Nothing has changed yet. A staff member will review this "
                    "request. Tell the user it is waiting for approval.",
                }
            else:
                output = execute(ToolContext(db, actor, run), tool, data)
                if tool.risk == Risk.NOTIFY:
                    db.flush()
                    audit(db, run, tool, data.model_dump(mode="json"), output)
        except ValidationError as exc:
            error = f"Invalid input: {exc.errors(include_url=False, include_context=False)}"
        except (AppError, PermissionError) as exc:
            db.rollback()
            error = exc.message if isinstance(exc, AppError) else str(exc)
        except Exception:
            db.rollback()
            logger.exception("Tool %s failed in run %s", block["name"], run.id)
            error = "The tool failed unexpectedly."

    db.add(call)  # again, in case a rollback above discarded it
    call.output = output
    call.error = error
    call.duration_ms = int((time.monotonic() - started) * 1000)
    result_block: dict[str, Any] = {"type": "tool_result", "tool_use_id": block["id"]}
    if error:
        result_block |= {"content": error, "is_error": True}
        event = Event("tool_finished", {"tool": block["name"], "ok": False, "error": error})
    else:
        result_block["content"] = json.dumps(output, default=str)
        event = (
            Event("approval", {"tool": block["name"], "approval_request": approval.id})
            if approval
            else Event("tool_finished", {"tool": block["name"], "ok": True})
        )
    return result_block, event


def _finish(db: Session, run: AgentRun, status: RunStatus, text: str, error: str | None = None):
    pending = db.scalar(
        select(ApprovalRequest.id).where(
            ApprovalRequest.run_id == run.id, ApprovalRequest.status == ApprovalStatus.PENDING
        )
    )
    if status == RunStatus.FINISHED and pending:
        status = RunStatus.WAITING
    run.status = status
    run.output = text
    run.error = error
    run.finished_at = datetime.now(UTC)
    db.commit()
    return Event("done", {"run": run.id, "status": status.value, "text": text})


def run_stream(
    db: Session,
    agent: Agent,
    actor: Actor,
    message: str,
    model: Model,
    conversation_id: str | None = None,
) -> Iterator[Event]:
    """Run the agent on a user message, yielding events as it goes.

    Pass the `conversation_id` of an earlier run to carry on that conversation.
    """
    run = AgentRun(
        agent=agent.name,
        conversation_id=conversation_id or str(uuid.uuid4()),
        actor_kind=actor.kind,
        customer_id=actor.customer_id,
        staff_id=actor.staff_id,
        status=RunStatus.RUNNING,
        input=message,
    )
    db.add(run)
    db.flush()
    messages = _history(db, run.conversation_id)
    user_message = {"role": "user", "content": [{"type": "text", "text": message}]}
    db.add(AgentMessage(run=run, role="user", content=user_message["content"]))
    db.commit()
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] = [*messages[-1]["content"], *user_message["content"]]
    else:
        messages.append(user_message)
    tools = agent.tools_for(actor)

    try:
        while True:
            if limit := _limit_reached(agent, run):
                yield _finish(db, run, RunStatus.STOPPED, LIMIT_REPLY, f"Stopped at the {limit}.")
                return
            request = ModelRequest(
                system=agent.system,
                messages=messages,
                tools=[tool.schema() for tool in tools],
                effort=agent.effort,
            )
            response: ModelResponse | None = None
            for kind, value in model.stream(request):
                if kind == "text":
                    yield Event("text", {"text": value})
                else:
                    response = value
            assert response is not None
            _record_response(db, run, response)
            messages.append({"role": "assistant", "content": response.content})
            db.commit()

            if response.stop_reason == "refusal":
                yield _finish(db, run, RunStatus.FAILED, FAILURE_REPLY, "The model declined.")
                return
            tool_uses = [b for b in response.content if b.get("type") == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses:
                yield _finish(db, run, RunStatus.FINISHED, _blocks_text(response.content))
                return

            reason = _blocks_text(response.content)
            results = []
            for block in tool_uses:
                yield Event("tool_started", {"tool": block["name"], "input": block.get("input")})
                result, event = _call_tool(db, agent, actor, run, block, reason)
                results.append(result)
                yield event
            # All results go back together in one user message.
            db.add(AgentMessage(run=run, role="user", content=results))
            messages.append({"role": "user", "content": results})
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Agent run %s failed", run.id)
        yield _finish(db, run, RunStatus.FAILED, FAILURE_REPLY, repr(exc))


def run(
    db: Session,
    agent: Agent,
    actor: Actor,
    message: str,
    model: Model,
    conversation_id: str | None = None,
) -> RunResult:
    events = list(run_stream(db, agent, actor, message, model, conversation_id))
    done = events[-1]
    result_run = db.get(AgentRun, done.data["run"])
    assert result_run is not None
    return RunResult(result_run, done.data["text"], events)
