from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import payhere
from app.models import Order, OrderStatus, PaymentEvent, StockAdjustment, StockReason
from app.services.orders import move, release_expired_orders, send_missing_confirmations
from app.services.payments import fake_notification
from tests.test_checkout import DETAILS


@pytest.fixture
def placed(client, db, make_product):
    """A guest cart with two mugs, checked out. Returns (order, mug, cart headers)."""
    mug = make_product(price="1200", on_hand=5)
    cart = {"X-Cart-Token": client.post("/cart").json()["token"]}
    client.put(f"/cart/items/{mug.id}", json={"quantity": 2}, headers=cart)
    number = client.post("/checkout", json=DETAILS, headers=cart).json()["order_number"]
    order = db.scalar(select(Order).where(Order.order_number == number))
    return order, mug, cart


def notify(client, order, status_code=payhere.SUCCESS, **changes):
    fields = fake_notification(order.order_number, f"{order.total:.2f}", "LKR", status_code)
    fields.update(changes)
    response = client.post("/payments/payhere/notify", data=fields)
    assert response.status_code == 200
    return response


def events(db, order):
    return [e.outcome for e in db.scalars(select(PaymentEvent).order_by(PaymentEvent.id))]


def test_payment_marks_paid_takes_stock_and_sends_one_email_even_if_sent_twice(
    client, db, mailer, placed
):
    order, mug, cart = placed

    notify(client, order)
    notify(client, order)

    assert order.status == OrderStatus.PAID
    assert order.paid_at is not None
    assert order.payment_reference == f"FAKE-{order.order_number}"
    assert db.scalars(select(Order)).all() == [order]
    assert (mug.inventory.on_hand, mug.inventory.reserved) == (3, 0)
    sales = db.scalars(
        select(StockAdjustment).where(StockAdjustment.reason == StockReason.SALE)
    ).all()
    assert [(s.quantity_change, s.note) for s in sales] == [(-2, f"Order {order.order_number}")]
    assert len(mailer.sent) == 1
    assert mailer.sent[0].to == "guest@example.com"
    assert order.order_number in mailer.sent[0].subject
    assert order.access_key in mailer.sent[0].body
    assert order.confirmation_sent_at is not None
    assert events(db, order) == ["paid", "duplicate"]
    assert [e.to_status for e in order.events] == [OrderStatus.PENDING, OrderStatus.PAID]
    # The cart is emptied.
    assert client.get("/cart", headers=cart).json()["items"] == []


def test_bad_signature_changes_nothing(client, db, mailer, placed):
    order, mug, _ = placed

    notify(client, order, md5sig="0" * 32)

    assert order.status == OrderStatus.PENDING
    assert mug.inventory.reserved == 2
    assert mailer.sent == []
    event = db.scalar(select(PaymentEvent))
    assert (event.signature_valid, event.outcome, event.order_id) == (
        False,
        "invalid_signature",
        None,
    )


def test_tampered_amount_fails_the_signature(client, db, placed):
    order, _, _ = placed
    notify(client, order, payhere_amount="1.00")
    assert order.status == OrderStatus.PENDING
    assert events(db, order) == ["invalid_signature"]


def test_signed_but_wrong_amount_is_flagged(client, db, placed):
    order, _, _ = placed
    fields = fake_notification(order.order_number, "1.00", "LKR", payhere.SUCCESS)
    client.post("/payments/payhere/notify", data=fields)

    assert order.status == OrderStatus.PENDING
    assert order.needs_attention is not None
    assert events(db, order) == ["amount_mismatch"]


def test_unknown_order_is_logged(client, db):
    fields = fake_notification("DT-NOPE00", "100.00", "LKR", payhere.SUCCESS)
    client.post("/payments/payhere/notify", data=fields)
    assert db.scalar(select(PaymentEvent)).outcome == "unknown_order"


@pytest.mark.parametrize("status_code", [payhere.CANCELLED, payhere.FAILED])
def test_cancel_or_failure_releases_stock(client, db, mailer, placed, status_code):
    order, mug, _ = placed

    notify(client, order, status_code)

    assert order.status == OrderStatus.CANCELLED
    assert (mug.inventory.on_hand, mug.inventory.reserved) == (5, 0)
    assert mailer.sent == []


def test_pending_status_waits(client, placed):
    order, _, _ = placed
    notify(client, order, payhere.PENDING)
    assert order.status == OrderStatus.PENDING


def test_failure_after_payment_is_ignored(client, placed):
    order, mug, _ = placed
    notify(client, order)
    notify(client, order, payhere.FAILED)
    assert order.status == OrderStatus.PAID
    assert mug.inventory.on_hand == 3


def test_chargeback_is_flagged(client, placed):
    order, _, _ = placed
    notify(client, order)
    notify(client, order, payhere.CHARGEBACK)
    assert order.status == OrderStatus.PAID
    assert "chargeback" in order.needs_attention


def test_expired_orders_release_their_stock(db, placed):
    order, mug, _ = placed

    assert release_expired_orders(db) == 0
    later = datetime.now(UTC) + timedelta(minutes=31)
    assert release_expired_orders(db, now=later) == 1

    assert order.status == OrderStatus.CANCELLED
    assert order.events[-1].note == "Not paid in time"
    assert mug.inventory.reserved == 0


def test_late_payment_is_accepted_when_stock_is_still_there(client, db, mailer, placed):
    order, mug, _ = placed
    release_expired_orders(db, now=datetime.now(UTC) + timedelta(minutes=31))

    notify(client, order)

    assert order.status == OrderStatus.PAID
    assert (mug.inventory.on_hand, mug.inventory.reserved) == (3, 0)
    assert len(mailer.sent) == 1
    assert events(db, order) == ["paid_late"]


def test_late_payment_without_stock_is_flagged_for_refund(client, db, mailer, placed):
    order, mug, _ = placed
    release_expired_orders(db, now=datetime.now(UTC) + timedelta(minutes=31))
    mug.inventory.on_hand = 1
    db.flush()

    notify(client, order)
    notify(client, order)

    assert order.status == OrderStatus.CANCELLED
    assert "Refund" in order.needs_attention
    assert mug.inventory.on_hand == 1
    assert mailer.sent == []
    assert events(db, order) == ["refund_needed", "duplicate"]


def test_failed_email_is_retried(client, db, mailer, placed, monkeypatch):
    order, _, _ = placed

    def broken(_email):
        raise OSError("SMTP down")

    monkeypatch.setattr(mailer, "send", broken)
    notify(client, order)
    assert order.status == OrderStatus.PAID
    assert order.confirmation_sent_at is None

    monkeypatch.undo()
    assert send_missing_confirmations(db, mailer) == 1
    assert send_missing_confirmations(db, mailer) == 0
    assert len(mailer.sent) == 1


def test_status_rules(placed):
    order, _, _ = placed
    with pytest.raises(Exception, match="pending to shipped"):
        move(order, OrderStatus.SHIPPED, "")
    move(order, OrderStatus.CANCELLED, "")
    with pytest.raises(Exception, match="cancelled to paid"):
        move(order, OrderStatus.PAID, "")


def test_fake_gateway_pays_and_returns_to_the_storefront(client, db, mailer, placed):
    order, mug, cart = placed
    page = client.post("/payments/fake/checkout", data={"order_id": order.order_number})
    assert page.status_code == 200
    assert "Fake payment gateway" in page.text

    response = client.post(
        "/payments/fake/complete",
        data={
            "order_id": order.order_number,
            "amount": f"{order.total:.2f}",
            "currency": "LKR",
            "status_code": payhere.SUCCESS,
            "return_url": f"http://localhost:3000/order/{order.order_number}?key=k",
            "cancel_url": "http://localhost:3000/cart",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"http://localhost:3000/order/{order.order_number}"
    )
    assert order.status == OrderStatus.PAID
    assert len(mailer.sent) == 1


def test_fake_gateway_never_redirects_elsewhere(client, placed):
    order, _, _ = placed
    response = client.post(
        "/payments/fake/complete",
        data={
            "order_id": order.order_number,
            "status_code": "-1",
            "cancel_url": "https://evil.example",
        },
        follow_redirects=False,
    )
    assert response.headers["location"] == "http://localhost:3000"


def test_fake_gateway_is_off_with_payhere(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("PAYMENT_PROVIDER", "payhere")
    get_settings.cache_clear()
    try:
        assert client.post("/payments/fake/checkout").status_code == 404
    finally:
        get_settings.cache_clear()


def test_worker_run_releases_and_retries(db, placed, monkeypatch, mailer):
    from app import worker

    order, _, _ = placed
    order.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()
    monkeypatch.setattr(worker, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker, "get_email_sender", lambda: mailer)

    worker.run_once()

    assert order.status == OrderStatus.CANCELLED
