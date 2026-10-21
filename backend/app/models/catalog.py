from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price >= 0", name="price_not_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(default=True)

    inventory: Mapped["Inventory"] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Inventory(TimestampMixin, Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("on_hand >= 0", name="on_hand_not_negative"),
        CheckConstraint("reserved >= 0 AND reserved <= on_hand", name="reserved_within_on_hand"),
        CheckConstraint("reorder_point >= 0", name="reorder_point_not_negative"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    on_hand: Mapped[int] = mapped_column(default=0)
    reserved: Mapped[int] = mapped_column(default=0)
    reorder_point: Mapped[int] = mapped_column(default=0)
    bin_location: Mapped[str | None] = mapped_column(String(50))

    product: Mapped[Product] = relationship(back_populates="inventory")
