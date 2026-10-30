"""Tracing for the console: agent runs, their conversations and what they cost."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import NotFound
from app.models import ActorKind, AgentMessage, AgentRun, AgentToolCall, RunStatus, Staff
from app.permissions import Permission, require
from app.schemas import (
    AgentMessageOut,
    AgentRunListOut,
    AgentRunSummaryOut,
    AgentToolCallOut,
    AgentTotalsOut,
    ConversationOut,
)

PAGE = 50


def _start_of_today() -> datetime:
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _totals(db: Session, since: datetime) -> dict[str | None, AgentTotalsOut]:
    """Totals since `since`, per agent and overall (under None)."""
    rows = db.execute(
        select(
            AgentRun.agent,
            func.count(),
            func.count().filter(AgentRun.status == RunStatus.FAILED),
            func.coalesce(func.sum(AgentRun.input_tokens + AgentRun.output_tokens), 0),
            func.coalesce(func.sum(AgentRun.cost), 0),
        )
        .where(AgentRun.started_at >= since)
        .group_by(AgentRun.agent)
    ).all()
    totals = {
        agent: AgentTotalsOut(runs=runs, failed=failed, tokens=tokens, cost=cost)
        for agent, runs, failed, tokens, cost in rows
    }
    totals[None] = AgentTotalsOut(
        runs=sum(t.runs for t in totals.values()),
        failed=sum(t.failed for t in totals.values()),
        tokens=sum(t.tokens for t in totals.values()),
        cost=sum((t.cost for t in totals.values()), Decimal(0)),
    )
    return totals


def list_runs(
    db: Session,
    staff: Staff,
    agent: str | None = None,
    status: RunStatus | None = None,
    before: int | None = None,
) -> AgentRunListOut:
    require(staff, Permission.VIEW_REPORTS, "You can't view agent runs.")
    query = select(AgentRun).order_by(AgentRun.id.desc()).limit(PAGE)
    if agent:
        query = query.where(AgentRun.agent == agent)
    if status:
        query = query.where(AgentRun.status == status)
    if before:
        query = query.where(AgentRun.id < before)
    week = _totals(db, _start_of_today() - timedelta(days=6))
    return AgentRunListOut(
        runs=[AgentRunSummaryOut.model_validate(run) for run in db.scalars(query)],
        today=_totals(db, _start_of_today())[None],
        last_7_days=week.pop(None),
        by_agent={name: totals for name, totals in week.items() if name},
    )


def get_conversation(db: Session, staff: Staff, run_id: int) -> ConversationOut:
    """The whole conversation the run belongs to: every run, message and tool call in it."""
    require(staff, Permission.VIEW_REPORTS, "You can't view agent runs.")
    run = db.get(AgentRun, run_id)
    if run is None:
        raise NotFound("Run not found.")
    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.conversation_id == run.conversation_id)
        .order_by(AgentRun.id)
    ).all()
    ids = [r.id for r in runs]
    messages = db.scalars(
        select(AgentMessage).where(AgentMessage.run_id.in_(ids)).order_by(AgentMessage.id)
    )
    calls = db.scalars(
        select(AgentToolCall).where(AgentToolCall.run_id.in_(ids)).order_by(AgentToolCall.id)
    )
    return ConversationOut(
        conversation_id=run.conversation_id,
        runs=[AgentRunSummaryOut.model_validate(r) for r in runs],
        messages=[AgentMessageOut.model_validate(m) for m in messages],
        tool_calls=[AgentToolCallOut.model_validate(c) for c in calls],
        cost=sum((r.cost for r in runs), Decimal(0)),
    )


def customer_spend_today(db: Session) -> Decimal:
    """What storefront agents have cost so far today (UTC), for the daily budget."""
    return db.scalar(
        select(func.coalesce(func.sum(AgentRun.cost), 0)).where(
            AgentRun.actor_kind == ActorKind.CUSTOMER, AgentRun.started_at >= _start_of_today()
        )
    )
