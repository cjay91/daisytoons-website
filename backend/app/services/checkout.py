"""Checkout: turn a cart into a pending order with its stock reserved, ready for payment."""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import payhere
from app.config import Settings, get_settings
from app.errors import Conflict
from app.models import Cart, CartItem, Customer, Order, OrderEvent, OrderItem, OrderStatus
from app.pricing import ZERO, delivery_fee, gift_wrap_fee, money
from app.schemas import CheckoutOut, CheckoutRequest, PaymentForm
from app.services.inventory import available, lock_inventories, reserve_stock
from app.services.orders import cancel_pending, order_link

# No 0/O or 1/I/L, so a number read out over the phone is never ambiguous.
ORDER_NUMBER_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _new_order_number(db: Session) -> str:
    while True:
        number = "DT-" + "".join(secrets.choice(ORDER_NUMBER_ALPHABET) for _ in range(6))
        if db.scalar(select(Order.id).where(Order.order_number == number)) is None:
            return number


def checkout(
    db: Session, cart: Cart, customer: Customer | None, data: CheckoutRequest
) -> CheckoutOut:
    settings = get_settings()
    email = data.email or (customer.email if customer else None)
    if email is None:
        raise Conflict("An email address is needed for the order confirmation.")

    # Lock the cart so the same cart can't be checked out twice at once.
    db.scalar(
        select(Cart)
        .where(Cart.id == cart.id)
        .with_for_update()
        # Locked rows are read fresh, not from what this session loaded before.
        .execution_options(populate_existing=True)
    )
    items = db.scalars(
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.product_id)
        .options(selectinload(CartItem.product))
    ).all()
    if not items:
        raise Conflict("Your cart is empty.")

    # An earlier unpaid order from this cart is replaced by this one; its stock goes back first.
    earlier = db.scalars(
        select(Order)
        .where(Order.cart_id == cart.id, Order.status == OrderStatus.PENDING)
        .options(selectinload(Order.items))
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    for order in earlier:
        cancel_pending(db, order, "Replaced by a new checkout")

    inventories = lock_inventories(db, [item.product_id for item in items])
    for item in items:
        product = item.product
        inventory = inventories.get(product.id)
        left = available(inventory) if inventory else 0
        if not product.is_active:
            raise Conflict(f"{product.name} is no longer available. Remove it to continue.")
        if item.quantity > left:
            raise Conflict(
                f"Only {left} of {product.name} left in stock. Change the quantity to continue."
            )

    order_items = [
        OrderItem(
            product_id=item.product_id,
            product_name=item.product.name,
            unit_price=item.product.price,
            quantity=item.quantity,
            line_total=money(item.product.price * item.quantity),
        )
        for item in items
    ]
    subtotal = money(sum((line.line_total for line in order_items), ZERO))
    wrap_fee = gift_wrap_fee(settings, cart.gift_wrap)
    delivery = delivery_fee(settings, subtotal, data.address.district)
    order = Order(
        order_number=_new_order_number(db),
        access_key=secrets.token_urlsafe(24),
        customer_id=customer.id if customer else None,
        cart_id=cart.id,
        email=email,
        customer_name=data.customer_name.strip(),
        phone=data.phone.strip(),
        status=OrderStatus.PENDING,
        subtotal=subtotal,
        gift_wrap=cart.gift_wrap,
        gift_wrap_fee=wrap_fee,
        gift_message=cart.gift_message if cart.gift_wrap else "",
        delivery_fee=delivery,
        total=subtotal + wrap_fee + delivery,
        shipping_address={**data.address.model_dump(), "country": "LK"},
        notes=data.notes,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.reservation_minutes),
        items=order_items,
        events=[OrderEvent(from_status=None, to_status=OrderStatus.PENDING, note="Checkout")],
    )
    for item in items:
        reserve_stock(inventories[item.product_id], item.quantity)
    db.add(order)
    db.commit()

    return CheckoutOut(
        order_number=order.order_number,
        order_key=order.access_key,
        total=order.total,
        currency=settings.currency,
        expires_at=order.expires_at,
        payment=payment_form(settings, order),
    )


def payment_form(settings: Settings, order: Order) -> PaymentForm:
    api = settings.api_public_url.rstrip("/")
    first_name, _, last_name = order.customer_name.partition(" ")
    address = order.shipping_address
    fields = {
        "merchant_id": settings.payhere_merchant_id,
        "return_url": order_link(order),
        "cancel_url": f"{settings.storefront_url.rstrip('/')}/cart",
        "notify_url": f"{api}/payments/payhere/notify",
        "order_id": order.order_number,
        "items": f"Daisytoons order {order.order_number}",
        "currency": settings.currency,
        "amount": payhere.format_amount(order.total),
        "first_name": first_name,
        "last_name": last_name or first_name,
        "email": order.email,
        "phone": order.phone,
        "address": ", ".join(filter(None, [address["line1"], address.get("line2")])),
        "city": address["city"],
        "country": "Sri Lanka",
        "hash": payhere.checkout_hash(settings, order.order_number, order.total, settings.currency),
    }
    if settings.payment_provider == "payhere":
        action_url = payhere.checkout_url(settings)
    else:
        action_url = f"{api}/payments/fake/checkout"
    return PaymentForm(action_url=action_url, fields=fields)
