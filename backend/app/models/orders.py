import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum
from app.models.catalog import Product


class OrderStatus(enum.StrEnum):
    PENDING = "pending"
    PAID = "paid"
    PACKING = "packing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Cart(TimestampMixin, Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Guests are identified by this random token; logged-in customers by customer_id.
    token: Mapped[str] = mapped_column(String(64), unique=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), unique=True
    )
    gift_wrap: Mapped[bool] = mapped_column(default=False)
    gift_message: Mapped[str] = mapped_column(String(300), default="")

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", order_by="CartItem.id"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    quantity: Mapped[int]

    cart: Mapped[Cart] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True)
    # A private key that lets the person who placed the order see it without logging in.
    access_key: Mapped[str] = mapped_column(String(64))
    # Empty for guest checkouts.
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    cart_id: Mapped[int | None] = mapped_column(
        ForeignKey("carts.id", ondelete="SET NULL"), index=True
    )
    email: Mapped[str] = mapped_column(String(320))
    customer_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(32))
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, "order_status"), default=OrderStatus.PENDING, index=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    gift_wrap: Mapped[bool] = mapped_column(default=False)
    gift_wrap_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    gift_message: Mapped[str] = mapped_column(String(300), default="")
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # A copy of the address at order time, so editing an address never changes past orders.
    shipping_address: Mapped[dict[str, Any]] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    # Unpaid orders are cancelled and their stock released after this time.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_reference: Mapped[str | None] = mapped_column(String(100))
    confirmation_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when something needs a person to look, such as a payment for an expired order.
    needs_attention: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    events: Mapped[list["OrderEvent"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderEvent.id"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    # Name and price are copied at order time.
    product_name: Mapped[str] = mapped_column(String(200))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int]
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")


class OrderEvent(Base):
    """Status history: one row per change of an order's status."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[OrderStatus | None] = mapped_column(
        str_enum(OrderStatus, "order_event_from_status")
    )
    to_status: Mapped[OrderStatus] = mapped_column(str_enum(OrderStatus, "order_event_to_status"))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="events")


class PaymentEvent(Base):
    """Every notification received from the payment gateway, kept as it arrived."""

    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    order_number: Mapped[str] = mapped_column(String(32), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    provider_payment_id: Mapped[str | None] = mapped_column(String(100))
    status_code: Mapped[str] = mapped_column(String(8))
    signature_valid: Mapped[bool]
    outcome: Mapped[str] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
