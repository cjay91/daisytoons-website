from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.agents.catalog import AGENTS
from app.agents.context import Actor
from app.agents.core import Limits, run, run_stream
from app.agents.evals import STOCK_HELPER_EVALS, World, run_scenario
from app.agents.model import (
    ClaudeModel,
    ModelRequest,
    ScriptedModel,
    Usage,
    cost,
    text,
    tool_use,
)
from app.agents.tools import registry
from app.errors import Conflict, Forbidden
from app.models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditEntry,
    RunStatus,
    StaffRole,
)
from app.services import approvals

AGENT = AGENTS["stock_helper"]


@pytest.mark.parametrize("scenario", STOCK_HELPER_EVALS, ids=lambda s: s.name)
def test_stock_helper_evals(db, scenario):
    result = run_scenario(db, scenario)
    assert result.passed, result.failures


@pytest.fixture
def world(db):
    world = World(db)
    world.product("bear", "Teddy bear, large", "3500", on_hand=8, reserved=2)
    return world


@pytest.fixture
def requested(db, world, make_staff):
    """A run that asked to set the bear's reorder point to 5, and the approval request."""
    actor = Actor.for_staff(make_staff(StaffRole.SUPPORT))
    bear = world.products["bear"]
    model = ScriptedModel(
        [
            [
                text("The bears sell fast."),
                tool_use("set_reorder_point", {"product_id": bear.id, "reorder_point": 5}),
            ],
            [text("Waiting for approval.")],
        ]
    )
    result = run(db, AGENT, actor, "Reorder bears at 5.", model)
    request = db.scalar(select(ApprovalRequest).where(ApprovalRequest.run_id == result.run.id))
    return result.run, request, bear


# Approvals


def test_approve_tool_waits_then_runs_once_as_the_approver(db, requested, make_staff):
    agent_run, request, bear = requested
    assert request.status == ApprovalStatus.PENDING
    assert request.reason == "The bears sell fast."
    assert bear.inventory.reorder_point == 0
    assert agent_run.status == RunStatus.WAITING

    admin = make_staff(StaffRole.ADMIN)
    approved = approvals.approve(db, admin, request.id, note="Fine")

    assert approved.status == ApprovalStatus.APPROVED
    assert approved.result == {"product_id": bear.id, "reorder_point": 5}
    assert bear.inventory.reorder_point == 5
    assert agent_run.status == RunStatus.FINISHED
    [entry] = db.scalars(select(AuditEntry).where(AuditEntry.run_id == agent_run.id))
    assert (entry.tool, entry.approved_by_id, entry.approval_id) == (
        "set_reorder_point",
        admin.id,
        request.id,
    )
    with pytest.raises(Conflict, match="already approved"):
        approvals.approve(db, admin, request.id)
    assert len(db.scalars(select(AuditEntry)).all()) == 1


def test_approver_can_edit_the_input(db, requested, make_staff):
    _, request, bear = requested
    approvals.approve(
        db, make_staff(StaffRole.ADMIN), request.id, {"product_id": bear.id, "reorder_point": 3}
    )
    assert bear.inventory.reorder_point == 3
    assert request.input["reorder_point"] == 3


def test_rejected_requests_never_run(db, requested, make_staff):
    agent_run, request, bear = requested
    approvals.reject(db, make_staff(StaffRole.ADMIN), request.id, note="Not now")

    assert request.status == ApprovalStatus.REJECTED
    assert bear.inventory.reorder_point == 0
    assert agent_run.status == RunStatus.FINISHED
    with pytest.raises(Conflict):
        approvals.approve(db, make_staff(StaffRole.ADMIN), request.id)
    assert bear.inventory.reorder_point == 0


def test_only_staff_who_could_make_the_change_can_approve_it(db, requested, make_staff):
    _, request, bear = requested
    with pytest.raises(Forbidden):
        approvals.approve(db, make_staff(StaffRole.SUPPORT), request.id)
    assert bear.inventory.reorder_point == 0
    assert request.status == ApprovalStatus.PENDING


def test_expired_requests_cannot_be_approved(db, requested, make_staff):
    _, request, bear = requested
    request.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()

    with pytest.raises(Conflict, match="expired"):
        approvals.approve(db, make_staff(StaffRole.ADMIN), request.id)
    assert request.status == ApprovalStatus.EXPIRED
    assert bear.inventory.reorder_point == 0


def test_list_pending(db, requested, make_staff):
    _, request, _ = requested
    assert [r.id for r in approvals.list_pending(db)] == [request.id]
    approvals.reject(db, make_staff(StaffRole.ADMIN), request.id)
    assert approvals.list_pending(db) == []


# The loop


def test_run_is_traced_with_tokens_and_cost(db, world, make_staff):
    actor = Actor.for_staff(make_staff(StaffRole.PACKER))
    model = ScriptedModel(
        [[tool_use("get_stock", {"product_id": world.products["bear"].id})], [text("6 left.")]]
    )

    result = run(db, AGENT, actor, "Bears?", model)

    agent_run = result.run
    assert (agent_run.status, agent_run.output, agent_run.steps) == (
        RunStatus.FINISHED,
        "6 left.",
        2,
    )
    assert (agent_run.input_tokens, agent_run.output_tokens) == (2000, 200)
    assert agent_run.cost == 2 * cost("claude-opus-5-5", Usage(1000, 100))
    assert [m.role for m in agent_run.messages] == ["user", "assistant", "user", "assistant"]
    [call] = agent_run.tool_calls
    assert call.tool == "get_stock" and call.output["available"] == 6 and call.error is None
    assert agent_run.finished_at is not None


def test_stream_reports_text_tools_and_done(db, world, make_staff):
    actor = Actor.for_staff(make_staff(StaffRole.PACKER))
    model = ScriptedModel(
        [
            [text("Looking."), tool_use("search_products", {"query": "bear"})],
            [text("Found it.")],
        ]
    )

    events = list(run_stream(db, AGENT, actor, "Bears?", model))

    assert [e.type for e in events] == ["text", "tool_started", "tool_finished", "text", "done"]
    assert events[-1].data["status"] == "finished"


def test_customers_are_not_offered_staff_tools(db, world, make_customer):
    model = ScriptedModel([[text("Hello.")]])
    run(db, AGENT, Actor.for_customer(make_customer()), "Hi", model)
    assert [t["name"] for t in model.requests[0].tools] == ["search_products"]


def test_unknown_tools_and_bad_input_are_errors_for_the_model(db, world, make_staff):
    actor = Actor.for_staff(make_staff(StaffRole.ADMIN))
    model = ScriptedModel(
        [
            [
                tool_use("drop_tables", {}, "toolu_1"),
                tool_use("get_stock", {"product_id": "lots"}, "toolu_2"),
            ],
            [text("Sorry.")],
        ]
    )

    result = run(db, AGENT, actor, "Go", model)

    errors = [c.error for c in result.run.tool_calls]
    assert "no tool called drop_tables" in errors[0]
    assert errors[1].startswith("Invalid input")
    results = model.requests[1].messages[-1]["content"]
    assert [r["is_error"] for r in results] == [True, True]


def test_a_conversation_carries_on_across_runs(db, world, make_staff):
    actor = Actor.for_staff(make_staff(StaffRole.PACKER))
    first = run(db, AGENT, actor, "Hi", ScriptedModel([[text("Hello!")]]))
    model = ScriptedModel([[text("Still here.")]])

    second = run(db, AGENT, actor, "Are you there?", model, first.run.conversation_id)

    assert second.run.id != first.run.id
    sent = model.requests[0].messages
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[1]["content"] == [text("Hello!")]


def test_a_model_failure_fails_the_run_politely(db, world, make_staff):
    actor = Actor.for_staff(make_staff(StaffRole.PACKER))
    result = run(db, AGENT, actor, "Hi", ScriptedModel([]))
    assert result.run.status == RunStatus.FAILED
    assert "no turns left" in result.run.error
    assert result.text.startswith("Sorry")


def test_cost_limit_stops_a_run(db, world, make_staff):
    from dataclasses import replace

    agent = replace(AGENT, limits=Limits(cost=Decimal("0.001")))
    actor = Actor.for_staff(make_staff(StaffRole.PACKER))
    model = ScriptedModel([[tool_use("search_products", {"query": "bear"})], [text("Done")]])

    result = run(db, agent, actor, "Bears?", model)

    assert result.run.status == RunStatus.STOPPED
    assert "cost limit" in result.run.error
    assert len(model.requests) == 1


def test_tool_schemas_are_plain_json_schema():
    schema = registry.get("set_reorder_point").schema()
    assert schema["name"] == "set_reorder_point"
    assert schema["input_schema"]["required"] == ["product_id", "reorder_point"]
    assert schema["input_schema"]["additionalProperties"] is False


# The real model's wrapper, with a fake SDK client


def test_claude_model_sends_the_request_and_reads_the_reply():
    sent = {}
    message = SimpleNamespace(
        content=[SimpleNamespace(model_dump=lambda **_: {"type": "text", "text": "Hi"})],
        stop_reason="end_turn",
        model="claude-opus-5-5",
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=100,
            cache_creation_input_tokens=None,
        ),
    )

    @contextmanager
    def stream(**kwargs):
        sent.update(kwargs)
        yield SimpleNamespace(text_stream=iter(["H", "i"]), get_final_message=lambda: message)

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    model = ClaudeModel("claude-opus-5-5", client=client)

    events = list(model.stream(ModelRequest("Be nice.", [], [], effort="low")))

    assert events[:2] == [("text", "H"), ("text", "i")]
    response = events[2][1]
    assert response.content == [{"type": "text", "text": "Hi"}]
    assert (response.usage.cache_read_tokens, response.usage.cache_write_tokens) == (100, 0)
    assert sent["thinking"] == {"type": "adaptive"}
    assert sent["output_config"] == {"effort": "low"}
    assert sent["fallbacks"] == "default"


def test_unknown_models_are_costed_at_the_highest_price():
    assert cost("claude-something-new", Usage(1_000_000, 0)) == Decimal("10")


def test_a_conversation_survives_a_run_that_failed_mid_tool_call(db, world, make_staff):
    actor = Actor.for_staff(make_staff(StaffRole.PACKER))

    first = run(
        db,
        AGENT,
        actor,
        "Bears?",
        ScriptedModel([[tool_use("search_products", {"query": "bear"}, "toolu_1")]]),
    )
    assert first.run.status == RunStatus.FAILED  # the script ran out after the tool call
    # As if the process died after the model asked for the tool but before its result was saved.
    tool_results = first.run.messages[-1]
    assert tool_results.content[0]["type"] == "tool_result"
    db.delete(tool_results)
    db.flush()
    model = ScriptedModel([[text("Hello again.")]])

    run(db, AGENT, actor, "Hi?", model, first.run.conversation_id)

    sent = model.requests[0].messages
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "toolu_1",
        "content": "Not run.",
        "is_error": True,
    }
