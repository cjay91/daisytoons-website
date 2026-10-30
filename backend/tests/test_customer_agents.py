import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.agents.catalog import AGENTS
from app.agents.context import Actor
from app.agents.core import run
from app.agents.evals import GIFT_CONCIERGE_EVALS, SUPPORT_EVALS, World, run_scenario
from app.agents.model import ScriptedModel, text, tool_use
from app.api.agents import get_agent_model, parse_suggestions
from app.config import get_settings
from app.models import ActorKind, AgentRun, OrderStatus, RunStatus, StaffRole


@pytest.mark.parametrize("scenario", GIFT_CONCIERGE_EVALS, ids=lambda s: s.name)
def test_gift_concierge_evals(db, scenario):
    result = run_scenario(db, scenario)
    assert result.passed, result.failures


@pytest.mark.parametrize("scenario", SUPPORT_EVALS, ids=lambda s: s.name)
def test_support_evals(db, scenario):
    result = run_scenario(db, scenario)
    assert result.passed, result.failures


def test_storefront_agents_only_get_customer_tools(db, make_customer):
    actor = Actor.for_customer(make_customer())
    assert [t.name for t in AGENTS["gift_concierge"].tools_for(actor)] == [
        "search_products",
        "search_knowledge",
        "add_to_cart",
        "contact_a_person",
    ]
    assert {t.audience for t in AGENTS["support"].tools_for(actor)} == {"anyone"}
    assert AGENTS["gift_message"].tools_for(actor) == []


# The tools, one at a time


def call(db, actor, tool, tool_input):
    """Run one tool through a scripted run; returns (output, error)."""
    model = ScriptedModel([[tool_use(tool, tool_input)], [text("OK")]])
    agent = AGENTS["support"] if tool != "add_to_cart" else AGENTS["gift_concierge"]
    result = run(db, agent, actor, "?", model)
    [tool_call] = result.run.tool_calls
    return tool_call.output, tool_call.error


@pytest.fixture
def world(db):
    world = World(db)
    world.product("bear", "Teddy bear", "3500", on_hand=8)
    return world


def test_order_numbers_and_emails_match_loosely(db, world):
    order = world.order("o", "Me@Example.com", OrderStatus.PAID, [("bear", 1)])
    output, error = call(
        db,
        Actor.for_customer(),
        "get_order_status",
        {"order_number": f" {order.order_number.lower()} ", "email": "me@example.COM "},
    )
    assert error is None
    assert output["status"] == "paid" and output["items"] == [{"name": "Teddy bear", "quantity": 1}]
    assert "phone" not in output and "shipping_address" not in output


def test_a_wrong_email_and_a_missing_order_look_the_same(db, world):
    order = world.order("o", "me@example.com", OrderStatus.PAID, [("bear", 1)])
    guest = Actor.for_customer()
    _, wrong_email = call(
        db, guest, "get_order_status", {"order_number": order.order_number, "email": "x@y.com"}
    )
    _, no_email = call(db, guest, "get_order_status", {"order_number": order.order_number})
    _, missing = call(
        db, guest, "get_order_status", {"order_number": "DT-NOPE00", "email": "me@example.com"}
    )
    assert wrong_email == no_email == missing
    assert "No order matches" in missing


def test_guests_have_no_order_list(db):
    _, error = call(db, Actor.for_customer(), "get_my_orders", {})
    assert "isn't logged in" in error


def test_my_orders_are_only_mine(db, world, make_customer):
    me, someone = make_customer(), make_customer()
    mine = world.order("mine", me.email, OrderStatus.PAID, [("bear", 1)], customer=me)
    world.order("theirs", someone.email, OrderStatus.PAID, [("bear", 1)], customer=someone)
    output, _ = call(db, Actor.for_customer(me), "get_my_orders", {})
    assert [o["order_number"] for o in output] == [mine.order_number]


@pytest.mark.parametrize(
    ("status", "delivered_days_ago", "message"),
    [
        (OrderStatus.PACKING, None, "hasn't been sent yet"),
        (OrderStatus.REFUNDED, None, "already refunded"),
        (OrderStatus.DELIVERED, 30, "outside the returns window"),
    ],
)
def test_returns_only_for_orders_that_can_be_returned(
    db, world, status, delivered_days_ago, message
):
    tracking = "PR-1" if delivered_days_ago else None
    order = world.order(
        "o", "me@example.com", status, [("bear", 1)], None, tracking, delivered_days_ago
    )
    _, error = call(
        db,
        Actor.for_customer(),
        "start_return",
        {"order_number": order.order_number, "email": "me@example.com", "reason": "Too big"},
    )
    assert message in error
    db.refresh(order)
    assert order.needs_attention is None


def test_a_return_keeps_an_existing_flag_and_is_only_requested_once(db, world):
    order = world.order(
        "o", "me@example.com", OrderStatus.DELIVERED, [("bear", 1)], None, "PR-1", 1
    )
    order.needs_attention = "Customer called."
    db.flush()
    lookup = {"order_number": order.order_number, "email": "me@example.com", "reason": "Torn"}

    first, _ = call(db, Actor.for_customer(), "start_return", lookup)
    second, _ = call(db, Actor.for_customer(), "start_return", lookup)

    assert (first["status"], second["status"]) == ("requested", "already_requested")
    db.refresh(order)
    assert order.needs_attention == (
        "Customer called.\nReturn requested by the customer in chat: Torn"
    )


def test_add_to_cart_adds_to_the_guests_own_cart(db, world):
    world.me = world.actor("guest")
    bear = world.products["bear"]
    call(db, world.me, "add_to_cart", {"product_id": bear.id, "quantity": 2})
    output, _ = call(db, world.me, "add_to_cart", {"product_id": bear.id})
    assert output["quantity_in_cart"] == 3
    assert world.cart_items() == {"bear": 3}


def test_add_to_cart_needs_the_guests_cart(db, world):
    _, error = call(db, Actor.for_customer(None, "no-such-token"), "add_to_cart", {"product_id": 1})
    assert "Couldn't find the customer's cart" in error


def test_contact_offers_whatsapp_when_the_shop_has_it(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "shop_whatsapp", "94771234567")
    output, _ = call(db, Actor.for_customer(), "contact_a_person", {"summary": "Late order"})
    assert output["email"] == "orders@daisytoons.lk"
    assert output["email_link"] == "mailto:orders@daisytoons.lk?subject=Late%20order"
    assert output["whatsapp_link"] == "https://wa.me/94771234567?text=Late%20order"


# The chat API


def use_model(client, model):
    client.app.dependency_overrides[get_agent_model] = lambda: model


def events(response):
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


def test_status_is_off_without_a_model(client):
    use_model(client, None)
    body = client.get("/agents/status").json()
    assert body["enabled"] is False
    assert body["contact"]["email"] == "orders@daisytoons.lk"
    response = client.post("/agents/chat", json={"agent": "support", "message": "Hi"})
    assert response.status_code == 503


def test_chat_streams_and_carries_the_conversation_on(client, db):
    model = ScriptedModel(
        [
            [tool_use("search_knowledge", {"query": "gift wrap"})],
            [text("Yes, we gift wrap.")],
            [text("You're welcome.")],
        ]
    )
    use_model(client, model)
    assert client.get("/agents/status").json()["enabled"] is True

    first = client.post("/agents/chat", json={"agent": "gift_concierge", "message": "Wrap?"})
    assert first.headers["content-type"].startswith("text/event-stream")
    sent = events(first)
    assert [e["type"] for e in sent] == ["start", "tool", "text", "done"]
    assert sent[1] == {"type": "tool", "tool": "search_knowledge", "ok": True}
    assert sent[-1]["text"] == "Yes, we gift wrap."
    conversation = sent[0]["conversation_id"]

    again = client.post(
        "/agents/chat",
        json={"agent": "gift_concierge", "message": "Thanks", "conversation_id": conversation},
    )
    assert events(again)[0]["conversation_id"] == conversation
    assert len(model.requests[2].messages) == 5
    runs = db.scalars(select(AgentRun).where(AgentRun.conversation_id == conversation)).all()
    assert [(r.actor_kind, r.status) for r in runs] == [
        (ActorKind.CUSTOMER, RunStatus.FINISHED)
    ] * 2


def test_someone_elses_conversation_starts_a_new_one(client, db, make_customer):
    from tests.conftest import auth_headers

    model = ScriptedModel([[text("Hello.")], [text("Hello again.")]])
    use_model(client, model)
    alice = auth_headers("customer", make_customer().id)
    first = events(
        client.post("/agents/chat", json={"agent": "support", "message": "Hi"}, headers=alice)
    )
    conversation = first[0]["conversation_id"]

    other = events(
        client.post(
            "/agents/chat",
            json={"agent": "support", "message": "Hi", "conversation_id": conversation},
        )
    )
    assert other[0]["conversation_id"] != conversation
    assert len(model.requests[1].messages) == 1


def test_chat_adds_to_a_guests_cart(client, make_product):
    bear = make_product()
    token = client.post("/cart").json()["token"]
    use_model(
        client,
        ScriptedModel([[tool_use("add_to_cart", {"product_id": bear.id})], [text("Added.")]]),
    )
    response = client.post(
        "/agents/chat",
        json={"agent": "gift_concierge", "message": "Add the bear"},
        headers={"X-Cart-Token": token},
    )
    assert events(response)[1] == {"type": "tool", "tool": "add_to_cart", "ok": True}
    cart = client.get("/cart", headers={"X-Cart-Token": token}).json()
    assert [(i["product_id"], i["quantity"]) for i in cart["items"]] == [(bear.id, 1)]


def test_chat_only_offers_the_storefront_agents(client):
    use_model(client, ScriptedModel([]))
    response = client.post("/agents/chat", json={"agent": "stock_helper", "message": "Hi"})
    assert response.status_code == 422


def test_chat_is_rate_limited(client):
    use_model(client, ScriptedModel([[text("Hi.")]] * 41))
    codes = [
        client.post("/agents/chat", json={"agent": "support", "message": "Hi"}).status_code
        for _ in range(41)
    ]
    assert codes[:40] == [200] * 40 and codes[40] == 429


def test_chat_stops_at_the_daily_budget(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "customer_agents_daily_budget", Decimal("0.01"))
    db.add(
        AgentRun(
            agent="support",
            conversation_id="spent",
            actor_kind=ActorKind.CUSTOMER,
            status=RunStatus.FINISHED,
            input="Hi",
            cost=Decimal("0.02"),
        )
    )
    db.flush()
    use_model(client, ScriptedModel([[text("Hi.")]]))
    assert client.get("/agents/status").json()["enabled"] is False
    response = client.post("/agents/chat", json={"agent": "support", "message": "Hi"})
    assert response.status_code == 503


# Gift messages


def test_gift_message_suggestions(client):
    reply = (
        "Here you go:\n"
        '- "Happy birthday, Amma! Thank you for every cup of tea and every hug."\n'
        "- Wishing you the happiest of birthdays.\n"
        f"- {'x' * 301}\n"
        "2. Another one for you.\n"
    )
    model = ScriptedModel([[text(reply)]])
    use_model(client, model)

    response = client.post(
        "/agents/gift-message",
        json={"occasion": "Birthday", "recipient": "My mum", "tone": "warm", "details": "Tea"},
    )

    assert response.json()["suggestions"] == [
        "Happy birthday, Amma! Thank you for every cup of tea and every hug.",
        "Wishing you the happiest of birthdays.",
        "Another one for you.",
    ]
    sent = model.requests[0]
    assert sent.tools == []
    assert sent.messages[0]["content"][0]["text"] == (
        "Occasion: Birthday\nFor: My mum\nTone: warm\nDetails: Tea"
    )


def test_gift_message_without_suggestions_is_an_error(client):
    use_model(client, ScriptedModel([[text("Sorry, I can't.")]]))
    response = client.post("/agents/gift-message", json={"occasion": "Birthday"})
    assert response.status_code == 503


def test_parse_suggestions_keeps_three():
    assert parse_suggestions("- a\n- b\n- c\n- d") == ["a", "b", "c"]


# Tracing in the console


def test_staff_see_runs_with_costs(client, db, staff_headers):
    use_model(client, ScriptedModel([[text("Hello.")]]))
    conversation = events(client.post("/agents/chat", json={"agent": "support", "message": "Hi"}))[
        0
    ]["conversation_id"]
    admin = staff_headers(StaffRole.ADMIN)

    listing = client.get("/staff/agent-runs", headers=admin).json()

    [latest, *_] = listing["runs"]
    assert (latest["agent"], latest["conversation_id"], latest["output"]) == (
        "support",
        conversation,
        "Hello.",
    )
    assert listing["today"]["runs"] >= 1
    assert Decimal(listing["by_agent"]["support"]["cost"]) > 0

    detail = client.get(f"/staff/agent-runs/{latest['id']}", headers=admin).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["input_tokens"] == 1000
    assert Decimal(detail["cost"]) == Decimal(latest["cost"])


def test_only_staff_who_see_reports_see_runs(client, staff_headers):
    assert (
        client.get("/staff/agent-runs", headers=staff_headers(StaffRole.PACKER)).status_code == 403
    )
    assert client.get("/staff/agent-runs").status_code == 401


def test_a_run_from_last_week_is_counted_in_the_week(db, make_staff):
    from app.services.agent_runs import list_runs

    db.add(
        AgentRun(
            agent="support",
            conversation_id="old",
            actor_kind=ActorKind.CUSTOMER,
            status=RunStatus.FAILED,
            input="Hi",
            cost=Decimal("0.10"),
            started_at=datetime.now(UTC) - timedelta(days=3),
        )
    )
    db.flush()
    listing = list_runs(db, make_staff(StaffRole.ADMIN))
    assert listing.last_7_days.failed == 1
    assert listing.today.runs == 0
