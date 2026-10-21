from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import Conflict, InvalidCredentials
from app.models import Customer, Staff, StaffRole
from app.permissions import Permission, require
from app.security import hash_password, verify_password


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_customer(
    db: Session, *, email: str, password: str, full_name: str, phone: str | None = None
) -> Customer:
    email = normalize_email(email)
    if db.scalar(select(Customer.id).where(Customer.email == email)) is not None:
        raise Conflict("An account with this email already exists.")
    customer = Customer(
        email=email, password_hash=hash_password(password), full_name=full_name, phone=phone
    )
    db.add(customer)
    db.commit()
    return customer


def authenticate_customer(db: Session, *, email: str, password: str) -> Customer:
    customer = db.scalar(select(Customer).where(Customer.email == normalize_email(email)))
    if not verify_password(password, customer.password_hash if customer else None):
        raise InvalidCredentials("Email or password is incorrect.")
    if not customer.is_active:
        raise InvalidCredentials("Email or password is incorrect.")
    return customer


def authenticate_staff(db: Session, *, email: str, password: str) -> Staff:
    staff = db.scalar(select(Staff).where(Staff.email == normalize_email(email)))
    if not verify_password(password, staff.password_hash if staff else None):
        raise InvalidCredentials("Email or password is incorrect.")
    if not staff.is_active:
        raise InvalidCredentials("Email or password is incorrect.")
    return staff


def _insert_staff(
    db: Session, *, email: str, password: str, full_name: str, role: StaffRole
) -> Staff:
    email = normalize_email(email)
    if db.scalar(select(Staff.id).where(Staff.email == email)) is not None:
        raise Conflict("A staff member with this email already exists.")
    staff = Staff(
        email=email, password_hash=hash_password(password), full_name=full_name, role=role
    )
    db.add(staff)
    db.commit()
    return staff


def create_staff(
    db: Session, actor: Staff, *, email: str, password: str, full_name: str, role: StaffRole
) -> Staff:
    require(actor, Permission.MANAGE_STAFF, "Only admins can add staff.")
    return _insert_staff(db, email=email, password=password, full_name=full_name, role=role)


def create_first_admin(db: Session, *, email: str, password: str, full_name: str) -> Staff:
    """Bootstrap path for the command line, used before any admin exists."""
    return _insert_staff(
        db, email=email, password=password, full_name=full_name, role=StaffRole.ADMIN
    )


def list_staff(db: Session, actor: Staff) -> list[Staff]:
    require(actor, Permission.MANAGE_STAFF, "Only admins can view staff accounts.")
    return list(db.scalars(select(Staff).order_by(Staff.id)))
