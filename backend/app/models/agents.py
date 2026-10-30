"""Agent runs, their conversation and tool calls, approvals, and the audit log (Part 8)."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.accounts import Staff
from app.models.base import Base, str_enum


class RunStatus(enum.StrEnum):
    RUNNING = "running"
    FINISHED = "finished"
    WAITING = "waiting"  # finished, with approval requests still undecided
    STOPPED = "stopped"  # hit a step, token or cost limit
    FAILED = "failed"


class ActorKind(enum.StrEnum):
    CUSTOMER = "customer"
    STAFF = "staff"


class Risk(enum.StrEnum):
    AUTO = "auto"  # runs straight away
    NOTIFY = "notify"  # runs straight away and is written to the audit log
    APPROVE = "approve"  # runs only after a staff member approves it


class ApprovalStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent: Mapped[str] = mapped_column(String(64), index=True)
    # Runs in the same conversation share this id, so a chat can carry on across runs.
    conversation_id: Mapped[str] = mapped_column(String(36), index=True)
    actor_kind: Mapped[ActorKind] = mapped_column(str_enum(ActorKind, "agent_actor_kind"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    status: Mapped[RunStatus] = mapped_column(str_enum(RunStatus, "agent_run_status"))
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[int] = mapped_column(default=0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal(0))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AgentMessage.id"
    )
    tool_calls: Mapped[list["AgentToolCall"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AgentToolCall.id"
    )


class AgentMessage(Base):
    """One message of the conversation. Assistant messages also trace the model call."""

    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(64))
    stop_reason: Mapped[str | None] = mapped_column(String(32))
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    cache_read_tokens: Mapped[int | None]
    cache_write_tokens: Mapped[int | None]
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    duration_ms: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[AgentRun] = relationship(back_populates="messages")


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    tool_use_id: Mapped[str] = mapped_column(String(64))
    tool: Mapped[str] = mapped_column(String(64))
    risk: Mapped[Risk | None] = mapped_column(str_enum(Risk, "agent_tool_risk"))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output: Mapped[Any] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[AgentRun] = relationship(back_populates="tool_calls")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    tool_call_id: Mapped[int] = mapped_column(ForeignKey("agent_tool_calls.id", ondelete="CASCADE"))
    tool: Mapped[str] = mapped_column(String(64))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ApprovalStatus] = mapped_column(
        str_enum(ApprovalStatus, "approval_status"), index=True
    )
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    result: Mapped[Any] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[AgentRun] = relationship()
    decided_by: Mapped[Staff | None] = relationship()


class AuditEntry(Base):
    """Every change an agent made: notify tools, and approve tools once approved."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))
    agent: Mapped[str] = mapped_column(String(64))
    tool: Mapped[str] = mapped_column(String(64))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[Any] = mapped_column(JSONB, nullable=True)
    actor_kind: Mapped[ActorKind] = mapped_column(str_enum(ActorKind, "audit_actor_kind"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    approval_id: Mapped[int | None] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="SET NULL")
    )
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
