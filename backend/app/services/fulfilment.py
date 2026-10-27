"""Staff work on orders: the order queue, packing, shipping, delivery, cancellations and refunds.

Refunds are made in the payment gateway's dashboard. The console records them here, against the
order, so the books and the stock stay right.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.email import Email, EmailSender
from app.errors import Conflict, NotFound
from app.models import (
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentEvent,
    Product,
    Refund,
    Shipment,
    Staff,
    StockReason,
)
from app.permissions import Permission, has_permission, require
from app.pricing import ZERO, money
from app.schemas import (
    OrderCancel,
    PaymentEventOut,
    PickListItem,
    PickListOut,
    PickOrderLine,
    RefundCreate,
    ShipmentCreate,
    StaffOrderListOut,
    StaffOrderOut,
    StaffOrderSummaryOut,
)
from app.services.inventory import add_stock, lock_inventories
from app.services.orders import cancel_pending, move, order_link

log = logging.getLogger(__name__)

S = OrderStatus

# Offered in the console. Any other courier name can be typed in.
COURIERS = [
    "Domex",
    "Pronto Lanka",
    "Koombiyo",
    "Prompt Xpress",
    "Sri Lanka Post",
    "Own delivery",
]

# The queue's default view: paid orders waiting to be packed or shipped.
OPEN_STATUSES = (S.PAID, S.PACKING)


def _detail_query():
    return select(Order).options(
        selectinload(Order.items),
        selectinload(Order.events).selectinload(OrderEvent.staff),
        selectinload(Order.shipment).selectinload(Shipment.staff),
        selectinload(Order.refunds).selectinload(Refund.staff),
    )


def _get(db: Session, order_number: str) -> Order:
    order = db.scalar(_detail_query().where(Order.order_number == order_number))
    if order is None:
        raise NotFound("Order not found.")
    return order


def _lock(db: Session, order_number: str) -> Order:
    order = db.scalar(
        _detail_query()
        .where(Order.order_number == order_number)
        .with_for_update(of=Order)
        # Locked rows are read fresh, not from what this session loaded before.
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise NotFound("Order not found.")
    return order


def refunded_total(order: Order) -> Decimal:
    return money(sum((refund.amount for refund in order.refunds), ZERO))


def money_received(order: Order) -> bool:
    """Paid, or paid after it had already been cancelled (a late payment needing a refund)."""
    return order.paid_at is not None or order.payment_reference is not None


def refundable(order: Order) -> Decimal:
    if not money_received(order):
        return ZERO
    return max(order.total - refunded_total(order), ZERO)


def actions(staff: Staff, order: Order) -> list[str]:
    """What this person can do to this order now."""
    can = []
    if has_permission(staff, Permission.FULFIL_ORDERS):
        if order.status == S.PAID:
            can.append("pack")
        if order.status in (S.PAID, S.PACKING):
            can.append("ship")
        if order.status == S.SHIPPED:
            can.append("deliver")
        if order.shipment is not None and order.status in (S.SHIPPED, S.DELIVERED):
            can.append("resend_tracking")
    if has_permission(staff, Permission.REFUND_ORDERS):
        if order.status in (S.PENDING, S.PAID, S.PACKING):
            can.append("cancel")
        if refundable(order) > 0:
            can.append("refund")
    if order.needs_attention and has_permission(staff, Permission.SUPPORT_ORDERS):
        can.append("resolve_attention")
    return can


def order_out(db: Session, staff: Staff, order: Order) -> StaffOrderOut:
    payment_events = db.scalars(
        select(PaymentEvent)
        .where(PaymentEvent.order_number == order.order_number)
        .order_by(PaymentEvent.id)
    ).all()
    fields = {key: getattr(order, key) for key in StaffOrderOut.model_fields if hasattr(order, key)}
    return StaffOrderOut.model_validate(
        {
            **fields,
            "payment_events": [PaymentEventOut.model_validate(e) for e in payment_events],
            "refunded_total": refunded_total(order),
            "refundable": refundable(order),
            "actions": actions(staff, order),
        },
        from_attributes=True,
    )


# The queue


def list_orders(
    db: Session,
    actor: Staff,
    *,
    status: OrderStatus | None = None,
    q: str | None = None,
    needs_attention: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> StaffOrderListOut:
    """Without a status or search, the queue shows paid orders waiting to go out, oldest first,
    so the order that has waited longest is packed first. Anything else is newest first."""
    require(actor, Permission.VIEW_ORDERS, "Your role cannot view orders.")
    query = select(Order)
    if needs_attention:
        query = query.where(Order.needs_attention.is_not(None))
    if status is not None:
        query = query.where(Order.status == status)
    elif not q and not needs_attention:
        query = query.where(Order.status.in_(OPEN_STATUSES))
    for word in (q or "").split()[:5]:
        pattern = f"%{word.replace('%', '').replace('_', '')}%"
        query = query.where(
            or_(
                Order.order_number.ilike(pattern),
                Order.email.ilike(pattern),
                Order.customer_name.ilike(pattern),
                Order.phone.ilike(pattern),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    oldest_first = status in OPEN_STATUSES or (status is None and not q and not needs_attention)
    order_by = (
        (func.coalesce(Order.paid_at, Order.created_at), Order.id)
        if oldest_first
        else (Order.created_at.desc(), Order.id.desc())
    )
    orders = db.scalars(
        query.options(selectinload(Order.items)).order_by(*order_by).limit(limit).offset(offset)
    ).all()
    return StaffOrderListOut(
        total=total,
        orders=[
            StaffOrderSummaryOut(
                order_number=order.order_number,
                status=order.status,
                customer_name=order.customer_name,
                email=order.email,
                district=order.shipping_address.get("district", ""),
                total=order.total,
                item_count=sum(item.quantity for item in order.items),
                gift_wrap=order.gift_wrap,
                needs_attention=order.needs_attention,
                created_at=order.created_at,
                paid_at=order.paid_at,
            )
            for order in orders
        ],
    )


def get_order(db: Session, actor: Staff, order_number: str) -> Order:
    require(actor, Permission.VIEW_ORDERS, "Your role cannot view orders.")
    return _get(db, order_number)


# Packing and shipping


def start_packing(db: Session, actor: Staff, order_numbers: list[str]) -> list[str]:
    """Move paid orders to packing. Orders already being packed are left as they are, so a
    second click does no harm. Returns the orders now in packing."""
    require(actor, Permission.FULFIL_ORDERS, "Your role cannot pack orders.")
    packing = []
    for number in sorted(set(order_numbers)):
        order = _lock(db, number)
        if order.status == S.PAID:
            move(order, S.PACKING, "Packing started", staff_id=actor.id)
        elif order.status != S.PACKING:
            raise Conflict(f"Order {number} is {order.status}, so it can't be packed.")
        packing.append(number)
    db.commit()
    return packing


def pick_list(db: Session, actor: Staff, order_numbers: list[str] | None = None) -> PickListOut:
    """Everything to take off the shelves for the given orders (by default, every order being
    packed), added up per product and sorted by bin so one walk round the shelves gets it all."""
    require(actor, Permission.VIEW_ORDERS, "Your role cannot view orders.")
    query = select(Order).options(selectinload(Order.items))
    if order_numbers:
        query = query.where(Order.order_number.in_(order_numbers))
    else:
        query = query.where(Order.status == S.PACKING)
    orders = db.scalars(query.order_by(Order.paid_at, Order.id)).all()

    lines: dict[int, list[tuple[str, OrderItem]]] = {}
    for order in orders:
        for item in order.items:
            lines.setdefault(item.product_id, []).append((order.order_number, item))
    products = {
        p.id: p
        for p in db.scalars(
            select(Product).where(Product.id.in_(lines)).options(selectinload(Product.inventory))
        )
    }
    items = [
        PickListItem(
            product_id=product_id,
            sku=products[product_id].sku,
            name=products[product_id].name,
            bin_location=(
                products[product_id].inventory.bin_location
                if products[product_id].inventory
                else None
            ),
            quantity=sum(item.quantity for _, item in entries),
            orders=[PickOrderLine(order_number=n, quantity=item.quantity) for n, item in entries],
        )
        for product_id, entries in lines.items()
    ]
    # Items without a bin go last.
    items.sort(key=lambda i: (i.bin_location is None, i.bin_location or "", i.name))
    return PickListOut(order_numbers=[o.order_number for o in orders], items=items)


def shipped_email(order: Order) -> Email:
    shipment = order.shipment
    assert shipment is not None
    lines = [
        f"Hi {order.customer_name},",
        "",
        f"Good news: your order {order.order_number} is on its way.",
        "",
        f"Courier: {shipment.courier}",
        f"Tracking number: {shipment.tracking_number}",
        *([f"Track it: {shipment.tracking_url}"] if shipment.tracking_url else []),
        "",
    ]
    for item in order.items:
        lines.append(f"  {item.quantity} x {item.product_name}")
    address = order.shipping_address
    lines += [
        "",
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
        subject=f"Your Daisytoons order {order.order_number} has shipped",
        body="\n".join(lines),
    )


def send_tracking_email(db: Session, mailer: EmailSender, order_id: int, *, again=False) -> bool:
    """Email the customer their tracking details, once (or again, when staff ask). The order is
    locked while sending, so two senders can't both send it."""
    order = db.scalar(
        _detail_query()
        .where(Order.id == order_id)
        .with_for_update(of=Order)
        .execution_options(populate_existing=True)
    )
    shipment = order.shipment if order else None
    if shipment is None or (shipment.notified_at is not None and not again):
        db.commit()
        return False
    try:
        mailer.send(shipped_email(order))
    except Exception:
        # The worker tries again later (send_missing_tracking_emails).
        log.exception("Could not send the shipping email for %s", order.order_number)
        db.rollback()
        return False
    shipment.notified_at = datetime.now(UTC)
    db.commit()
    return True


def send_missing_tracking_emails(db: Session, mailer: EmailSender) -> int:
    order_ids = db.scalars(
        select(Shipment.order_id)
        .join(Order)
        .where(Shipment.notified_at.is_(None), Order.status == S.SHIPPED)
    ).all()
    return sum(send_tracking_email(db, mailer, order_id) for order_id in order_ids)


def ship(
    db: Session, mailer: EmailSender, actor: Staff, order_number: str, data: ShipmentCreate
) -> Order:
    """Hand a packed order to the courier and email the customer the tracking number."""
    require(actor, Permission.FULFIL_ORDERS, "Your role cannot ship orders.")
    order = _lock(db, order_number)
    if order.status == S.PAID:
        move(order, S.PACKING, "Packing started", staff_id=actor.id)
    if order.status != S.PACKING:
        raise Conflict(f"Order {order_number} is {order.status}, so it can't be shipped.")
    move(order, S.SHIPPED, f"Shipped with {data.courier.strip()}", staff_id=actor.id)
    order.shipment = Shipment(
        courier=data.courier.strip(),
        tracking_number=data.tracking_number.strip(),
        tracking_url=data.tracking_url,
        staff_id=actor.id,
        shipped_at=datetime.now(UTC),
    )
    db.commit()
    # After the commit, so the email only goes out for a shipment that was saved.
    send_tracking_email(db, mailer, order.id)
    return _get(db, order_number)


def resend_tracking(db: Session, mailer: EmailSender, actor: Staff, order_number: str) -> Order:
    require(actor, Permission.FULFIL_ORDERS, "Your role cannot ship orders.")
    order = _get(db, order_number)
    if order.shipment is None:
        raise Conflict(f"Order {order_number} hasn't shipped yet.")
    if not send_tracking_email(db, mailer, order.id, again=True):
        raise Conflict("The email could not be sent. Try again in a minute.")
    return _get(db, order_number)


def mark_delivered(db: Session, actor: Staff, order_number: str) -> Order:
    require(actor, Permission.FULFIL_ORDERS, "Your role cannot update deliveries.")
    order = _lock(db, order_number)
    move(order, S.DELIVERED, "Delivered", staff_id=actor.id)
    if order.shipment is not None:
        order.shipment.delivered_at = datetime.now(UTC)
    db.commit()
    return _get(db, order_number)


# Cancellations and refunds


def _restock(db: Session, actor: Staff, order: Order, reason: StockReason) -> None:
    """Put an order's items back on the shelf, each with its own log entry."""
    inventories = lock_inventories(db, [item.product_id for item in order.items])
    for item in order.items:
        add_stock(
            db,
            inventories[item.product_id],
            actor,
            item.quantity,
            reason,
            f"Order {order.order_number}",
        )


def cancel_order(db: Session, actor: Staff, order_number: str, data: OrderCancel) -> Order:
    """Cancel an order that hasn't shipped. An unpaid order's held stock is released. A paid
    order's items go back on the shelf and its full refund is recorded."""
    require(actor, Permission.REFUND_ORDERS, "Your role cannot cancel orders.")
    order = _lock(db, order_number)
    note = f"Cancelled by staff: {data.reason.strip()}"
    if order.status == S.PENDING:
        cancel_pending(db, order, note)
        order.events[-1].staff_id = actor.id
    elif order.status in (S.PAID, S.PACKING):
        move(order, S.CANCELLED, note, staff_id=actor.id)
        _restock(db, actor, order, StockReason.ORDER_CANCELLED)
        amount = refundable(order)
        if amount > 0:
            order.refunds.append(
                Refund(
                    amount=amount,
                    reason=data.reason.strip(),
                    reference=data.refund_reference,
                    restocked=True,
                    staff_id=actor.id,
                )
            )
    else:
        raise Conflict(f"Order {order_number} is {order.status}, so it can't be cancelled.")
    db.commit()
    return _get(db, order_number)


def refund_order(db: Session, actor: Staff, order_number: str, data: RefundCreate) -> Order:
    """Record a refund. A partial refund leaves the order where it is. A full refund marks it
    refunded, and can put the items back on the shelf (as returned, when it had shipped)."""
    require(actor, Permission.REFUND_ORDERS, "Your role cannot refund orders.")
    order = _lock(db, order_number)
    left = refundable(order)
    if left == 0:
        raise Conflict(f"Order {order_number} has nothing left to refund.")
    if data.amount > left:
        raise Conflict(f"Only Rs {left:,.2f} of order {order_number} is left to refund.")
    full = data.amount == left
    if data.restock and not full:
        raise Conflict("Items can only go back on the shelf with a full refund.")
    if data.restock and order.status not in (S.PAID, S.PACKING, S.SHIPPED, S.DELIVERED):
        raise Conflict(f"Order {order_number} is {order.status}; its stock is already back.")

    reason = data.reason.strip()
    if full and order.status in (S.PAID, S.PACKING, S.SHIPPED, S.DELIVERED):
        if data.restock:
            shipped = order.status in (S.SHIPPED, S.DELIVERED)
            _restock(
                db, actor, order, StockReason.RETURNED if shipped else StockReason.ORDER_CANCELLED
            )
        move(order, S.REFUNDED, f"Refunded: {reason}", staff_id=actor.id)
    order.refunds.append(
        Refund(
            amount=data.amount,
            reason=reason,
            reference=data.reference,
            restocked=data.restock,
            staff_id=actor.id,
        )
    )
    if full and order.status == S.CANCELLED:
        # A late payment for a cancelled order: once refunded, nothing is left to look at.
        order.needs_attention = None
    db.commit()
    return _get(db, order_number)


def resolve_attention(db: Session, actor: Staff, order_number: str) -> Order:
    require(actor, Permission.SUPPORT_ORDERS, "Your role cannot clear order flags.")
    order = _lock(db, order_number)
    order.needs_attention = None
    db.commit()
    return _get(db, order_number)
