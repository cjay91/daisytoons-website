import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum


class TagKind(enum.StrEnum):
    OCCASION = "occasion"
    RECIPIENT = "recipient"


class StockReason(enum.StrEnum):
    RECEIVED = "received"
    COUNT = "count"
    DAMAGED = "damaged"
    RETURNED = "returned"
    CORRECTION = "correction"
    IMPORT = "import"


product_tags = Table(
    "product_tags",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("kind", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[TagKind] = mapped_column(str_enum(TagKind, "tag_kind"))
    slug: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))


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
    tags: Mapped[list[Tag]] = relationship(secondary=product_tags, order_by=Tag.name)
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.position",
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(50))
    alt_text: Mapped[str] = mapped_column(String(300), default="")
    # 0 is the main photo.
    position: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[Product] = relationship(back_populates="images")


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
    # Change on_hand only through services.inventory.adjust_stock, which logs every change.
    on_hand: Mapped[int] = mapped_column(default=0)
    reserved: Mapped[int] = mapped_column(default=0)
    reorder_point: Mapped[int] = mapped_column(default=0)
    bin_location: Mapped[str | None] = mapped_column(String(50))

    product: Mapped[Product] = relationship(back_populates="inventory")


class StockAdjustment(Base):
    """An append-only log of every change to stock on hand."""

    __tablename__ = "stock_adjustments"
    __table_args__ = (
        CheckConstraint("on_hand_after = on_hand_before + quantity_change", name="change_adds_up"),
        CheckConstraint("on_hand_after >= 0", name="on_hand_after_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    # Empty when the change came from the import script rather than a staff member.
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    reason: Mapped[StockReason] = mapped_column(str_enum(StockReason, "stock_reason"))
    quantity_change: Mapped[int]
    on_hand_before: Mapped[int]
    on_hand_after: Mapped[int]
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
