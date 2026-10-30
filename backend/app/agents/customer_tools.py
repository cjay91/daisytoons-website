"""Tools for the storefront agents: the visitor's own cart, their own orders, and a person.

Every tool works only on what belongs to the visitor the run is for. That is checked here, in
code, from the run's actor, never from anything the model says: an order is found only for the
customer who placed it, or for someone who gives its number with the email it was placed with.
Not having an order and not being allowed to see it get the same answer.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.agents.tools import Tool, ToolContext, registry
from app.config import get_settings
from app.errors import AppError, Conflict, NotFound
from app.models import Order, OrderStatus, Product, Risk
from app.services import carts

NOT_FOUND = (
    "No order matches that order number and email. Check both with the customer; the number "
    "is in the confirmation email and starts with DT-."
)
RECENT_ORDERS = 5


class LoginNeeded(AppError):
    status_code = 403
    code = "login_needed"


class AddToCart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0, description="The product_id from search_products.")
    quantity: int = Field(default=1, ge=1, le=carts.MAX_PER_PRODUCT)


class NoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_number: str = Field(
        min_length=3, max_length=32, description="The order number, such as DT-7KQ3XM."
    )
    email: str | None = Field(
        default=None,
        max_length=320,
        description="The email the order was placed with, as the customer gave it. Needed "
        "unless the customer is logged in and the order is theirs.",
    )


class StartReturn(OrderLookup):
    reason: str = Field(
        min_length=3, max_length=1000, description="What the customer says is wrong, or why."
    )


class ContactPerson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        default="",
        max_length=500,
        description="One line on what the customer needs, to start their email with.",
    )


def _add_to_cart(ctx: ToolContext, data: AddToCart) -> dict[str, Any]:
    actor = ctx.actor
    if actor.customer is not None:
        cart = carts.get_or_create_cart(ctx.db, actor.customer, actor.cart_token)
    else:
        # The storefront gives every chatting guest a cart before the chat starts.
        cart = carts.find_cart(ctx.db, None, actor.cart_token)
        if cart is None:
            raise Conflict("Couldn't find the customer's cart. Ask them to add it on its page.")
    current = next((i.quantity for i in cart.items if i.product_id == data.product_id), 0)
    quantity = min(current + data.quantity, carts.MAX_PER_PRODUCT)
    carts.set_item(ctx.db, cart, data.product_id, quantity)
    product = ctx.db.get(Product, data.product_id)
    assert product is not None
    return {
        "added": product.name,
        "quantity_in_cart": quantity,
        "cart_items": sum(item.quantity for item in cart.items),
        "cart_url": "/cart",
    }


def _order_out(order: Order) -> dict[str, Any]:
    shipment = order.shipment
    return {
        "order_number": order.order_number,
        "status": order.status.value,
        "placed": order.created_at.date().isoformat(),
        "paid": order.paid_at is not None,
        "items": [{"name": i.product_name, "quantity": i.quantity} for i in order.items],
        "total": str(order.total),
        "gift_wrap": order.gift_wrap,
        "delivery_district": order.shipping_address.get("district"),
        "shipment": (
            {
                "courier": shipment.courier,
                "tracking_number": shipment.tracking_number,
                "tracking_url": shipment.tracking_url,
                "shipped": shipment.shipped_at.date().isoformat(),
                "delivered": shipment.delivered_at.date().isoformat()
                if shipment.delivered_at
                else None,
            }
            if shipment
            else None
        ),
        "return_requested": bool(order.needs_attention)
        and "Return requested" in (order.needs_attention or ""),
    }


def find_order(ctx: ToolContext, order_number: str, email: str | None) -> Order:
    """The order, if the actor may see it: theirs when logged in, or the email matches."""
    order = ctx.db.scalar(
        select(Order)
        .where(func.upper(Order.order_number) == order_number.strip().upper())
        .options(selectinload(Order.items), selectinload(Order.shipment))
    )
    if order is None:
        raise NotFound(NOT_FOUND)
    customer_id = ctx.actor.customer_id
    owns = customer_id is not None and order.customer_id == customer_id
    email_matches = email is not None and email.strip().lower() == order.email.strip().lower()
    if not (owns or email_matches):
        raise NotFound(NOT_FOUND)
    return order


def _get_my_orders(ctx: ToolContext, _: NoInput) -> list[dict[str, Any]]:
    if ctx.actor.customer is None:
        raise LoginNeeded(
            "The customer isn't logged in. Ask for the order number and the email the order "
            "was placed with."
        )
    orders = ctx.db.scalars(
        select(Order)
        .where(Order.customer_id == ctx.actor.customer.id)
        .options(selectinload(Order.items), selectinload(Order.shipment))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(RECENT_ORDERS)
    )
    return [_order_out(order) for order in orders]


def _get_order_status(ctx: ToolContext, data: OrderLookup) -> dict[str, Any]:
    return _order_out(find_order(ctx, data.order_number, data.email))


def _start_return(ctx: ToolContext, data: StartReturn) -> dict[str, Any]:
    order = find_order(ctx, data.order_number, data.email)
    settings = get_settings()
    delivered_at = order.shipment.delivered_at if order.shipment else None
    if order.status in (OrderStatus.PENDING, OrderStatus.PAID, OrderStatus.PACKING):
        raise Conflict(
            "This order hasn't been sent yet, so it can't be returned. The customer can ask "
            "the team to cancel it instead."
        )
    if order.status in (OrderStatus.CANCELLED, OrderStatus.REFUNDED):
        raise Conflict(f"This order is already {order.status.value}.")
    if delivered_at and datetime.now(UTC) - delivered_at > timedelta(days=settings.return_days):
        raise Conflict(
            f"This order was delivered more than {settings.return_days} days ago, so it is "
            "outside the returns window. The team may still help: offer contact_a_person."
        )
    if order.needs_attention and "Return requested" in order.needs_attention:
        return {"order_number": order.order_number, "status": "already_requested"}
    note = f"Return requested by the customer in chat: {data.reason.strip()}"
    order.needs_attention = f"{order.needs_attention}\n{note}" if order.needs_attention else note
    ctx.db.commit()
    return {
        "order_number": order.order_number,
        "status": "requested",
        "next": f"The team will email {order.email} within one working day with where to send "
        "the items. Nothing is refunded until they arrive back, unless the item was damaged "
        "or wrong.",
    }


def _contact_a_person(ctx: ToolContext, data: ContactPerson) -> dict[str, Any]:
    return contact_options(data.summary)


def contact_options(summary: str = "") -> dict[str, Any]:
    settings = get_settings()
    subject = quote(summary or "Help with my order")
    options: dict[str, Any] = {
        "email": settings.shop_email,
        "email_link": f"mailto:{settings.shop_email}?subject={subject}",
        "hours": "Monday to Saturday, 9am to 6pm. Emails are answered within one working day.",
    }
    if settings.shop_whatsapp:
        options["whatsapp_link"] = f"https://wa.me/{settings.shop_whatsapp}?text={subject}"
    return options


registry.add(
    Tool(
        "add_to_cart",
        "Add a product to the customer's cart. Only when the customer has asked for that "
        "product to be added. Stock is checked; a sold-out product is an error.",
        AddToCart,
        _add_to_cart,
        audience="anyone",
    )
)
registry.add(
    Tool(
        "get_my_orders",
        "The logged-in customer's five most recent orders, with status and tracking. An error "
        "if they aren't logged in.",
        NoInput,
        _get_my_orders,
        audience="anyone",
    )
)
registry.add(
    Tool(
        "get_order_status",
        "One order's status, items and tracking, by its number. A guest must also give the "
        "email the order was placed with.",
        OrderLookup,
        _get_order_status,
        audience="anyone",
    )
)
registry.add(
    Tool(
        "start_return",
        "Ask the team to start a return for a sent or delivered order. Only once the customer "
        "has said they want to return it and why. The team then emails them; nothing is "
        "refunded here.",
        StartReturn,
        _start_return,
        risk=Risk.NOTIFY,
        audience="anyone",
    )
)
registry.add(
    Tool(
        "contact_a_person",
        "How to reach a person at the shop: email, and WhatsApp when the shop has it. Use it "
        "whenever the customer asks for a person, or you can't help.",
        ContactPerson,
        _contact_a_person,
        audience="anyone",
    )
)
