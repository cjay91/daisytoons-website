"""A logged-in customer's own orders and saved addresses."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.errors import NotFound
from app.models import Address, Customer, Order
from app.schemas import AddressIn, OrderSummaryOut


def list_orders(db: Session, customer: Customer) -> list[OrderSummaryOut]:
    orders = db.scalars(
        select(Order)
        .where(Order.customer_id == customer.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    return [
        OrderSummaryOut(
            order_number=order.order_number,
            status=order.status,
            total=order.total,
            item_count=sum(item.quantity for item in order.items),
            created_at=order.created_at,
        )
        for order in orders
    ]


def get_order(db: Session, customer: Customer, order_number: str) -> Order:
    order = db.scalar(
        select(Order).where(Order.order_number == order_number, Order.customer_id == customer.id)
    )
    if order is None:
        raise NotFound("Order not found.")
    return order


def list_addresses(db: Session, customer: Customer) -> list[Address]:
    return list(
        db.scalars(
            select(Address)
            .where(Address.customer_id == customer.id)
            .order_by(Address.is_default.desc(), Address.id)
        )
    )


def _get_address(db: Session, customer: Customer, address_id: int) -> Address:
    address = db.get(Address, address_id)
    if address is None or address.customer_id != customer.id:
        raise NotFound("Address not found.")
    return address


def _apply(db: Session, customer: Customer, address: Address, data: AddressIn) -> None:
    values = data.model_dump()
    address.region = values.pop("district")
    for field, value in values.items():
        setattr(address, field, value)
    address.country = "LK"
    has_default = db.scalar(
        select(Address.id).where(
            Address.customer_id == customer.id, Address.is_default, Address.id != address.id
        )
    )
    if data.is_default:
        # Only one default address.
        db.execute(
            update(Address)
            .where(Address.customer_id == customer.id, Address.id != address.id)
            .values(is_default=False)
        )
    elif has_default is None:
        # The first address is the default.
        address.is_default = True


def create_address(db: Session, customer: Customer, data: AddressIn) -> Address:
    address = Address(customer_id=customer.id)
    db.add(address)
    _apply(db, customer, address, data)
    db.commit()
    return address


def update_address(db: Session, customer: Customer, address_id: int, data: AddressIn) -> Address:
    address = _get_address(db, customer, address_id)
    _apply(db, customer, address, data)
    db.commit()
    return address


def delete_address(db: Session, customer: Customer, address_id: int) -> None:
    address = _get_address(db, customer, address_id)
    was_default = address.is_default
    db.delete(address)
    db.flush()
    if was_default:
        replacement = db.scalar(
            select(Address).where(Address.customer_id == customer.id).order_by(Address.id)
        )
        if replacement is not None:
            replacement.is_default = True
    db.commit()
