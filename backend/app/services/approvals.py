"""Approving or rejecting what an agent asked to do. An approved tool runs once, as the approver."""

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.agents.catalog  # noqa: F401  (registers every tool)
from app.agents.context import Actor
from app.agents.core import audit, execute
from app.agents.tools import ToolContext, registry
from app.errors import AppError, Conflict, Forbidden, NotFound
from app.models import ApprovalRequest, ApprovalStatus, RunStatus, Staff


def list_pending(db: Session) -> list[ApprovalRequest]:
    return list(
        db.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.PENDING)
            .order_by(ApprovalRequest.id)
        )
    )


def _lock(db: Session, request_id: int) -> ApprovalRequest:
    request = db.scalar(
        select(ApprovalRequest)
        .where(ApprovalRequest.id == request_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if request is None:
        raise NotFound("Approval request not found.")
    if request.status == ApprovalStatus.PENDING and request.expires_at <= datetime.now(UTC):
        request.status = ApprovalStatus.EXPIRED
        db.commit()
        raise Conflict("This request has expired.")
    if request.status != ApprovalStatus.PENDING:
        raise Conflict(f"This request was already {request.status.value}.")
    return request


def _settle_run(db: Session, request: ApprovalRequest) -> None:
    """A run waiting on approvals is finished once none are left pending."""
    run = request.run
    if run.status == RunStatus.WAITING and not any(
        r.status == ApprovalStatus.PENDING
        for r in db.scalars(select(ApprovalRequest).where(ApprovalRequest.run_id == run.id))
    ):
        run.status = RunStatus.FINISHED


def approve(
    db: Session,
    staff: Staff,
    request_id: int,
    edited_input: dict[str, Any] | None = None,
    note: str | None = None,
) -> ApprovalRequest:
    """Run the requested tool with its input (or the approver's edit of it), exactly once."""
    request = _lock(db, request_id)
    tool = registry.get(request.tool)
    if tool is None:
        raise Conflict(f"The tool {request.tool} no longer exists.")
    actor = Actor.for_staff(staff)
    if not actor.allows(tool.permission):
        raise Forbidden("Your role cannot approve this.")
    try:
        data = tool.input_model.model_validate(
            request.input if edited_input is None else edited_input
        )
    except ValidationError as exc:
        raise AppError(f"Invalid input: {exc.errors(include_url=False)}") from exc

    request.input = data.model_dump(mode="json")
    request.status = ApprovalStatus.APPROVED
    request.decided_by_id = staff.id
    request.decided_at = datetime.now(UTC)
    request.note = note
    db.flush()
    run = request.run
    try:
        request.result = execute(ToolContext(db, actor, run), tool, data)
    except AppError as exc:
        # The tool refused, for example because stock changed meanwhile. The decision stands
        # and isn't retried; the error is kept so staff can see why.
        db.rollback()
        request = _lock_after_failure(db, request_id, staff, note, exc.message)
        _settle_run(db, request)
        db.commit()
        return request
    audit(db, run, tool, request.input, request.result, approval=request)
    _settle_run(db, request)
    db.commit()
    return request


def _lock_after_failure(
    db: Session, request_id: int, staff: Staff, note: str | None, error: str
) -> ApprovalRequest:
    request = _lock(db, request_id)
    request.status = ApprovalStatus.APPROVED
    request.decided_by_id = staff.id
    request.decided_at = datetime.now(UTC)
    request.note = note
    request.error = error
    return request


def reject(db: Session, staff: Staff, request_id: int, note: str | None = None) -> ApprovalRequest:
    request = _lock(db, request_id)
    tool = registry.get(request.tool)
    if tool is not None and not Actor.for_staff(staff).allows(tool.permission):
        raise Forbidden("Your role cannot decide this.")
    request.status = ApprovalStatus.REJECTED
    request.decided_by_id = staff.id
    request.decided_at = datetime.now(UTC)
    request.note = note
    _settle_run(db, request)
    db.commit()
    return request
