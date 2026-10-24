"""Payment notifications from the gateway. Each one is checked, logged in payment_events and
applied to its order at most once."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app import payhere
from app.config import get_settings
from app.email import EmailSender
from app.models import Cart, Order, OrderStatus, PaymentEvent
from app.services.inventory import available, lock_inventories, record_sale, reserve_stock
from app.services.orders import cancel_pending, lock_order, move, send_confirmation


def _amount_matches(order: Order, fields: dict[str, str]) -> bool:
    try:
        amount = Decimal(fields.get("payhere_amount", ""))
    except InvalidOperation:
        return False
    return amount == order.total and fields.get("payhere_currency") == get_settings().currency


def _complete_sale(db: Session, order: Order, payment_id: str | None, note: str, **kw) -> None:
    """Mark the order paid and take its reserved stock off the shelf."""
    move(order, OrderStatus.PAID, note, **kw)
    order.paid_at = datetime.now(UTC)
    order.payment_reference = payment_id
    order.expires_at = None
    inventories = lock_inventories(db, [item.product_id for item in order.items])
    for item in order.items:
        record_sale(db, inventories[item.product_id], item.quantity, f"Order {order.order_number}")
    cart = db.get(Cart, order.cart_id) if order.cart_id else None
    if cart is not None:
        cart.items.clear()


def _late_payment(db: Session, order: Order, payment_id: str | None) -> str:
    """Money arrived for an order that was already cancelled, usually because it expired."""
    inventories = lock_inventories(db, [item.product_id for item in order.items])
    if all(available(inventories[i.product_id]) >= i.quantity for i in order.items):
        for item in order.items:
            reserve_stock(inventories[item.product_id], item.quantity)
        _complete_sale(db, order, payment_id, "Paid after the order had expired", late_payment=True)
        return "paid_late"
    order.payment_reference = payment_id
    order.needs_attention = (
        "Payment received after the order was cancelled, and the stock is no longer "
        "available. Refund the customer."
    )
    return "refund_needed"


def _apply(db: Session, order: Order, fields: dict[str, str]) -> str:
    status_code = fields.get("status_code", "")
    payment_id = fields.get("payment_id") or None
    if status_code == payhere.SUCCESS:
        if order.status == OrderStatus.PENDING:
            _complete_sale(db, order, payment_id, "Payment received")
            return "paid"
        if order.status == OrderStatus.CANCELLED and order.paid_at is None:
            if order.needs_attention is not None:
                return "duplicate"
            return _late_payment(db, order, payment_id)
        return "duplicate"
    if status_code in (payhere.CANCELLED, payhere.FAILED):
        if order.status == OrderStatus.PENDING:
            cancel_pending(db, order, "Payment cancelled or failed")
            return "cancelled"
        return "ignored"
    if status_code == payhere.CHARGEBACK:
        order.needs_attention = "The customer's bank reversed this payment (chargeback)."
        return "chargeback"
    return "ignored"


def handle_notification(
    db: Session, mailer: EmailSender, provider: str, fields: dict[str, str]
) -> str:
    """Check and apply one notification. Returns what happened, which is also logged."""
    settings = get_settings()
    order_number = fields.get("order_id", "")[:32]
    valid = payhere.signature_valid(settings, fields)
    order = lock_order(db, order_number) if valid else None
    if not valid:
        outcome = "invalid_signature"
    elif fields.get("merchant_id") != settings.payhere_merchant_id:
        outcome = "wrong_merchant"
    elif order is None:
        outcome = "unknown_order"
    elif not _amount_matches(order, fields):
        outcome = "amount_mismatch"
        order.needs_attention = "A payment notification didn't match the order total."
    else:
        outcome = _apply(db, order, fields)

    db.add(
        PaymentEvent(
            provider=provider,
            order_number=order_number,
            order_id=order.id if order else None,
            provider_payment_id=(fields.get("payment_id") or None),
            status_code=fields.get("status_code", "")[:8],
            signature_valid=valid,
            outcome=outcome,
            raw=fields,
        )
    )
    db.commit()

    # After the commit, so the email only goes out for a payment that was saved.
    if order is not None and order.status == OrderStatus.PAID:
        send_confirmation(db, mailer, order.id)
    return outcome


def fake_notification(order_number: str, amount: str, currency: str, status_code: str) -> dict:
    """What PayHere would send. Used by the built-in fake gateway and by tests."""
    settings = get_settings()
    fields = {
        "merchant_id": settings.payhere_merchant_id,
        "order_id": order_number,
        "payment_id": f"FAKE-{order_number}",
        "payhere_amount": amount,
        "payhere_currency": currency,
        "status_code": status_code,
        "status_message": "Fake gateway",
        "method": "TEST",
    }
    fields["md5sig"] = payhere.notification_signature(settings, fields)
    return fields
