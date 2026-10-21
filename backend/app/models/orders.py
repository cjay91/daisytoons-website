import enum
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum


class OrderStatus(enum.StrEnum):
    PENDING = "pending"
    PAID = "paid"
    PACKING = "packing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True)
    # Empty for guest checkouts.
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    email: Mapped[str] = mapped_column(String(320))
    status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, "order_status"), default=OrderStatus.PENDING, index=True
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # A copy of the address at order time, so editing an address never changes past orders.
    shipping_address: Mapped[dict[str, Any]] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
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
