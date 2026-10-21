import enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, str_enum


class StaffRole(enum.StrEnum):
    ADMIN = "admin"
    PACKER = "packer"
    SUPPORT = "support"


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True)

    addresses: Mapped[list["Address"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class Address(TimestampMixin, Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str | None] = mapped_column(String(50))
    recipient_name: Mapped[str] = mapped_column(String(200))
    line1: Mapped[str] = mapped_column(String(200))
    line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2))
    phone: Mapped[str | None] = mapped_column(String(32))
    is_default: Mapped[bool] = mapped_column(default=False)

    customer: Mapped[Customer] = relationship(back_populates="addresses")


class Staff(TimestampMixin, Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[StaffRole] = mapped_column(str_enum(StaffRole, "staff_role"))
    is_active: Mapped[bool] = mapped_column(default=True)
