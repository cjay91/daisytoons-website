"""Orders: the status rules, stock held for unpaid orders, expiry and the confirmation email."""

import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.email import Email, EmailSender
from app.errors import Conflict, NotFound
from app.models import Order, OrderEvent, OrderStatus
from app.services.inventory import lock_inventories, release_stock

log = logging.getLogger(__name__)

S = OrderStatus
# Every allowed move. Anything else is refused.
TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    S.PENDING: {S.PAID, S.CANCELLED},
    S.PAID: {S.PACKING, S.CANCELLED, S.REFUNDED},
    S.PACKING: {S.SHIPPED, S.CANCELLED, S.REFUNDED},
    S.SHIPPED: {S.DELIVERED, S.REFUNDED},
    S.DELIVERED: {S.REFUNDED},
    S.CANCELLED: set(),
    S.REFUNDED: set(),
}


def move(
    order: Order,
    to: OrderStatus,
    note: str,
    *,
    late_payment: bool = False,
    staff_id: int | None = None,
) -> None:
    """Change an order's status and record it in the history. A payment that arrives after
    the order was cancelled may move it from cancelled to paid (late_payment)."""
    allowed = TRANSITIONS[order.status] | ({S.PAID} if late_payment else set())
    if to not in allowed:
        raise Conflict(f"An order can't go from {order.status} to {to}.")
    order.events.append(
        OrderEvent(from_status=order.status, to_status=to, note=note, staff_id=staff_id)
    )
    order.status = to


def lock_order(db: Session, order_number: str) -> Order | None:
    return db.scalar(
        select(Order)
        .where(Order.order_number == order_number)
        .options(selectinload(Order.items))
        .with_for_update()
        # Locked rows are read fresh, not from what this session loaded before.
        .execution_options(populate_existing=True)
    )


def release_reservation(db: Session, order: Order) -> None:
    inventories = lock_inventories(db, [item.product_id for item in order.items])
    for item in order.items:
        release_stock(inventories[item.product_id], item.quantity)


def cancel_pending(db: Session, order: Order, note: str) -> None:
    """Cancel an unpaid order and release its stock. The caller has locked the order."""
    move(order, S.CANCELLED, note)
    order.expires_at = None
    release_reservation(db, order)


def release_expired_orders(db: Session, now: datetime | None = None) -> int:
    """Cancel unpaid orders past their reservation time. Returns how many."""
    now = now or datetime.now(UTC)
    orders = db.scalars(
        select(Order)
        .where(Order.status == S.PENDING, Order.expires_at < now)
        .order_by(Order.id)
        .options(selectinload(Order.items))
        # A payment being handled right now keeps its lock; that order is checked next time.
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    ).all()
    for order in orders:
        cancel_pending(db, order, "Not paid in time")
    db.commit()
    return len(orders)


def get_order_for_key(db: Session, order_number: str, key: str) -> Order:
    order = db.scalar(select(Order).where(Order.order_number == order_number))
    # The same answer for a wrong key and a missing order, so numbers can't be probed.
    if order is None or not secrets.compare_digest(order.access_key, key):
        raise NotFound("Order not found.")
    return order


def order_link(order: Order) -> str:
    base = get_settings().storefront_url.rstrip("/")
    return f"{base}/order/{order.order_number}?key={order.access_key}"


def confirmation_email(order: Order) -> Email:
    lines = [
        f"Hi {order.customer_name},",
        "",
        f"Thank you for your order {order.order_number}. We've received your payment.",
        "",
    ]
    for item in order.items:
        lines.append(f"  {item.quantity} x {item.product_name}  Rs {item.line_total:,.2f}")
    lines += ["", f"Subtotal: Rs {order.subtotal:,.2f}"]
    if order.gift_wrap:
        lines.append(f"Gift wrap: Rs {order.gift_wrap_fee:,.2f}")
    delivery = f"Rs {order.delivery_fee:,.2f}" if order.delivery_fee else "Free"
    lines += [f"Delivery: {delivery}", f"Total: Rs {order.total:,.2f}", ""]
    address = order.shipping_address
    lines += [
        "Delivering to:",
        f"  {order.customer_name}",
        f"  {address['line1']}",
        *([f"  {address['line2']}"] if address.get("line2") else []),
        f"  {address['city']}, {address['district']}",
        "",
        f"See your order: {order_link(order)}",
        "",
        "Daisytoons",
    ]
    return Email(
        to=order.email,
        subject=f"Your Daisytoons order {order.order_number}",
        body="\n".join(lines),
    )


def send_confirmation(db: Session, mailer: EmailSender, order_id: int) -> bool:
    """Send the confirmation email for a paid order, once. Safe to call again: the order row
    is locked while sending and records when the email went out."""
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None or order.status != S.PAID or order.confirmation_sent_at is not None:
        db.commit()
        return False
    try:
        mailer.send(confirmation_email(order))
    except Exception:
        # The worker tries again later (send_missing_confirmations).
        log.exception("Could not send the confirmation email for %s", order.order_number)
        db.rollback()
        return False
    order.confirmation_sent_at = datetime.now(UTC)
    db.commit()
    return True


def send_missing_confirmations(db: Session, mailer: EmailSender) -> int:
    """Retry confirmation emails that failed to send."""
    order_ids = db.scalars(
        select(Order.id).where(Order.status == S.PAID, Order.confirmation_sent_at.is_(None))
    ).all()
    return sum(send_confirmation(db, mailer, order_id) for order_id in order_ids)
