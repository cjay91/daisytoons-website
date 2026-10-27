from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import OrderStatus, StaffRole, StockAdjustment, StockReason
from app.services.fulfilment import send_missing_tracking_emails
from tests.test_payments import notify

ADMIN, PACKER, SUPPORT = StaffRole.ADMIN, StaffRole.PACKER, StaffRole.SUPPORT
SHIPMENT = {"courier": "Domex", "tracking_number": "DX123456", "tracking_url": "https://x.lk/t"}


@pytest.fixture
def admin(staff_headers):
    return staff_headers(ADMIN)


def post(client, headers, order, action, body=None, status=200):
    response = client.post(
        f"/staff/orders/{order.order_number}/{action}", json=body, headers=headers
    )
    assert response.status_code == status, response.json()
    return response.json()


def stock_log(db, product):
    return [
        (a.reason, a.quantity_change)
        for a in db.scalars(
            select(StockAdjustment)
            .where(StockAdjustment.product_id == product.id)
            .order_by(StockAdjustment.id)
        )
    ]


# The queue


def test_queue_shows_paid_orders_oldest_first(client, place_order, admin):
    first, second = place_order(), place_order()
    place_order(paid=False)

    body = client.get("/staff/orders", headers=admin).json()

    assert body["total"] == 2
    assert [o["order_number"] for o in body["orders"]] == [first.order_number, second.order_number]
    assert body["orders"][0]["item_count"] == 2
    assert body["orders"][0]["district"] == "Colombo"


def test_queue_filters_and_search(client, place_order, admin):
    paid = place_order()
    pending = place_order(paid=False)

    by_status = client.get("/staff/orders?status=pending", headers=admin).json()
    by_number = client.get(f"/staff/orders?q={pending.order_number.lower()}", headers=admin).json()
    by_name = client.get("/staff/orders?q=nimali", headers=admin).json()

    assert [o["order_number"] for o in by_status["orders"]] == [pending.order_number]
    assert [o["order_number"] for o in by_number["orders"]] == [pending.order_number]
    assert {o["order_number"] for o in by_name["orders"]} == {
        paid.order_number,
        pending.order_number,
    }


@pytest.mark.parametrize("role", [ADMIN, PACKER, SUPPORT])
def test_every_role_can_see_orders(client, place_order, staff_headers, role):
    order = place_order()
    response = client.get(f"/staff/orders/{order.order_number}", headers=staff_headers(role))
    assert response.status_code == 200


def test_customers_cannot_use_the_staff_queue(client, make_customer):
    from tests.conftest import auth_headers

    response = client.get("/staff/orders", headers=auth_headers("customer", make_customer().id))
    assert response.status_code == 401


def test_order_detail_has_history_payments_and_actions(client, place_order, admin, staff_headers):
    order = place_order(gift_message="Happy birthday!")

    body = client.get(f"/staff/orders/{order.order_number}", headers=admin).json()
    support = client.get(f"/staff/orders/{order.order_number}", headers=staff_headers(SUPPORT))

    assert [e["to_status"] for e in body["events"]] == ["pending", "paid"]
    assert body["payment_events"][0]["outcome"] == "paid"
    assert body["gift_message"] == "Happy birthday!"
    assert body["actions"] == ["pack", "ship", "cancel", "refund"]
    assert support.json()["actions"] == []
    assert body["refundable"] == str(order.total)


# Packing and shipping


def test_paid_order_goes_from_queue_to_shipped_with_tracking(
    client, db, mailer, place_order, staff_headers
):
    packer = staff_headers(PACKER)
    order = place_order()
    mailer.sent.clear()

    packed = post(client, packer, order, "pack")
    shipped = post(client, packer, order, "ship", SHIPMENT)

    assert packed["status"] == "packing"
    assert shipped["status"] == "shipped"
    assert shipped["shipment"]["tracking_number"] == "DX123456"
    assert shipped["shipment"]["notified_at"] is not None
    assert shipped["events"][-1]["staff"]["full_name"] == "Test packer"
    assert shipped["actions"] == ["deliver", "resend_tracking"]
    [email] = mailer.sent
    assert email.to == "guest@example.com"
    assert "has shipped" in email.subject
    assert "Domex" in email.body and "DX123456" in email.body and "https://x.lk/t" in email.body
    # The customer's own order page shows the tracking number too.
    public = client.get(f"/orders/{order.order_number}?key={order.access_key}").json()
    assert public["shipment"]["tracking_number"] == "DX123456"


def test_shipping_a_paid_order_packs_it_on_the_way(client, place_order, admin):
    order = place_order()
    body = post(client, admin, order, "ship", SHIPMENT)
    assert [e["to_status"] for e in body["events"]] == ["pending", "paid", "packing", "shipped"]


def test_unpaid_orders_cannot_be_packed_or_shipped(client, place_order, admin):
    order = place_order(paid=False)
    post(client, admin, order, "pack", status=409)
    post(client, admin, order, "ship", SHIPMENT, status=409)


def test_support_cannot_ship(client, place_order, staff_headers):
    order = place_order()
    post(client, staff_headers(SUPPORT), order, "ship", SHIPMENT, status=403)


def test_bulk_packing_is_safe_to_repeat(client, place_order, admin):
    orders = [place_order(), place_order()]
    numbers = [o.order_number for o in orders]

    first = client.post("/staff/orders/pack", json={"order_numbers": numbers}, headers=admin)
    again = client.post("/staff/orders/pack", json={"order_numbers": numbers}, headers=admin)

    assert first.status_code == again.status_code == 200
    assert {o.status for o in orders} == {OrderStatus.PACKING}
    assert [e.to_status for e in orders[0].events].count(OrderStatus.PACKING) == 1


def test_failed_shipping_email_is_retried_by_the_worker(client, db, mailer, place_order, admin):
    order = place_order()

    def broken(_email):
        raise OSError("SMTP down")

    original = mailer.send
    mailer.send = broken
    body = post(client, admin, order, "ship", SHIPMENT)
    assert body["status"] == "shipped" and body["shipment"]["notified_at"] is None

    mailer.send = original
    mailer.sent.clear()
    assert send_missing_tracking_emails(db, mailer) == 1
    assert send_missing_tracking_emails(db, mailer) == 0
    assert len(mailer.sent) == 1


def test_resend_tracking_and_mark_delivered(client, mailer, place_order, admin):
    order = place_order()
    post(client, admin, order, "ship", SHIPMENT)
    mailer.sent.clear()

    post(client, admin, order, "resend-tracking")
    delivered = post(client, admin, order, "deliver")

    assert len(mailer.sent) == 1
    assert delivered["status"] == "delivered"
    assert delivered["shipment"]["delivered_at"] is not None


def test_pick_list_adds_up_items_by_bin(client, db, make_product, place_order, admin):
    bear = make_product(on_hand=10)
    card = make_product(on_hand=10)
    bear.inventory.bin_location = "B-2"
    card.inventory.bin_location = "A-1"
    first = place_order((bear, 2), (card, 1))
    second = place_order((bear, 3))
    place_order((card, 4))  # paid but not being packed yet
    client.post(
        "/staff/orders/pack",
        json={"order_numbers": [first.order_number, second.order_number]},
        headers=admin,
    )

    body = client.get("/staff/pick-list", headers=admin).json()

    assert set(body["order_numbers"]) == {first.order_number, second.order_number}
    assert [(i["bin_location"], i["quantity"]) for i in body["items"]] == [("A-1", 1), ("B-2", 5)]
    assert {o["quantity"] for o in body["items"][1]["orders"]} == {2, 3}


# Cancellations and refunds


def test_cancelling_a_paid_order_restocks_and_records_the_refund(
    client, db, make_product, place_order, admin
):
    mug = make_product(price="1200", on_hand=5)
    order = place_order((mug, 2))
    assert mug.inventory.on_hand == 3

    body = post(
        client, admin, order, "cancel", {"reason": "Customer asked", "refund_reference": "R1"}
    )

    assert body["status"] == "cancelled"
    assert mug.inventory.on_hand == 5
    assert stock_log(db, mug)[-1] == (StockReason.ORDER_CANCELLED, 2)
    assert [(r["amount"], r["reference"]) for r in body["refunds"]] == [(str(order.total), "R1")]
    assert body["refundable"] == "0.00"
    assert body["events"][-1]["staff"] is not None


def test_cancelling_an_unpaid_order_releases_its_hold(client, make_product, place_order, admin):
    mug = make_product(on_hand=5)
    order = place_order((mug, 2), paid=False)
    assert mug.inventory.reserved == 2

    body = post(client, admin, order, "cancel", {"reason": "Duplicate"})

    assert body["status"] == "cancelled"
    assert body["refunds"] == []
    assert (mug.inventory.on_hand, mug.inventory.reserved) == (5, 0)


def test_shipped_orders_cannot_be_cancelled(client, place_order, admin):
    order = place_order()
    post(client, admin, order, "ship", SHIPMENT)
    post(client, admin, order, "cancel", {"reason": "Too late"}, status=409)


@pytest.mark.parametrize("role", [PACKER, SUPPORT])
def test_only_admins_cancel_and_refund(client, place_order, staff_headers, role):
    order = place_order()
    headers = staff_headers(role)
    post(client, headers, order, "cancel", {"reason": "x"}, status=403)
    post(client, headers, order, "refunds", {"amount": "100", "reason": "x"}, status=403)


def test_partial_then_full_refund(client, db, make_product, place_order, admin):
    mug = make_product(price="1200", on_hand=5)
    order = place_order((mug, 2))  # 2400 + 400 delivery
    post(client, admin, order, "ship", SHIPMENT)

    partial = post(client, admin, order, "refunds", {"amount": "400", "reason": "Late delivery"})
    assert partial["status"] == "shipped"
    assert partial["refundable"] == "2400.00"

    post(client, admin, order, "refunds", {"amount": "2400.01", "reason": "x"}, status=409)
    post(client, admin, order, "refunds", {"amount": "100", "reason": "x", "restock": True}, 409)

    full = post(
        client, admin, order, "refunds", {"amount": "2400", "reason": "Returned", "restock": True}
    )
    assert full["status"] == "refunded"
    assert full["refunded_total"] == "2800.00"
    assert mug.inventory.on_hand == 5
    assert stock_log(db, mug)[-1] == (StockReason.RETURNED, 2)
    post(client, admin, order, "refunds", {"amount": "1", "reason": "x"}, status=409)


def test_unpaid_orders_have_nothing_to_refund(client, place_order, admin):
    order = place_order(paid=False)
    post(client, admin, order, "refunds", {"amount": "1", "reason": "x"}, status=409)


def test_refunding_a_late_payment_clears_the_flag(client, db, make_product, place_order, admin):
    from datetime import UTC, datetime, timedelta

    from app.services.orders import release_expired_orders

    mug = make_product(price="1200", on_hand=2)
    order = place_order((mug, 2), paid=False)
    release_expired_orders(db, now=datetime.now(UTC) + timedelta(minutes=31))
    mug.inventory.on_hand = 1
    notify(client, order)
    assert order.needs_attention

    flagged = client.get("/staff/orders?needs_attention=true", headers=admin).json()
    body = post(client, admin, order, "refunds", {"amount": str(order.total), "reason": "No stock"})

    assert [o["order_number"] for o in flagged["orders"]] == [order.order_number]
    assert body["status"] == "cancelled"
    assert body["needs_attention"] is None
    assert mug.inventory.on_hand == 1


def test_support_can_clear_an_attention_flag(client, db, place_order, staff_headers):
    order = place_order()
    order.needs_attention = "Customer called about the address."
    db.flush()

    body = post(client, staff_headers(SUPPORT), order, "resolve-attention")

    assert body["needs_attention"] is None
    post(client, staff_headers(PACKER), order, "resolve-attention", status=403)


def test_refund_amount_must_be_positive(client, place_order, admin):
    order = place_order()
    post(client, admin, order, "refunds", {"amount": "0", "reason": "x"}, status=422)
    assert (
        Decimal(post(client, admin, order, "refunds", {"amount": "1", "reason": "x"})["refundable"])
        == order.total - 1
    )
