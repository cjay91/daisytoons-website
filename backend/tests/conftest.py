"""Test setup.

Tests run against a real Postgres database (TEST_DATABASE_URL), created fresh and migrated once
per test run. Each test runs inside a transaction that is rolled back, so tests never see each
other's data.
"""

import os
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import get_db
from app.email import MemorySender, get_email_sender
from app.main import create_app
from app.models import Customer, Inventory, Order, Product, Staff, StaffRole
from app.security import create_access_token, hash_password
from app.storage import MemoryStorage, get_storage

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://daisytoons:daisytoons@localhost:5432/daisytoons_test",
)


def recreate_database(url: str) -> None:
    """Drop and create the database named in `url`, connecting through the `postgres` database."""
    parsed = make_url(url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{parsed.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{parsed.database}"'))
    admin.dispose()


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logging"] = False
    return config


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    recreate_database(TEST_DATABASE_URL)
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with engine.connect() as connection:
        transaction = connection.begin()
        # Commits inside the code under test become savepoints, and everything is rolled back.
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        yield session
        session.close()
        transaction.rollback()


@pytest.fixture
def storage() -> MemoryStorage:
    return MemoryStorage()


@pytest.fixture
def mailer() -> MemorySender:
    return MemorySender()


@pytest.fixture
def client(db: Session, storage: MemoryStorage, mailer: MemorySender) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_email_sender] = lambda: mailer
    return TestClient(app)


# Smallest valid PNG header plus padding; enough for the image type check.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture
def make_staff(db: Session) -> Callable[..., Staff]:
    count = 0

    def make(role: StaffRole, email: str | None = None, *, is_active: bool = True) -> Staff:
        nonlocal count
        count += 1
        staff = Staff(
            email=email or f"{role.value}{count}@example.com",
            password_hash=hash_password("staff-password"),
            full_name=f"Test {role.value}",
            role=role,
            is_active=is_active,
        )
        db.add(staff)
        db.flush()
        return staff

    return make


def auth_headers(kind: str, subject_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(kind, subject_id)}"}


@pytest.fixture
def staff_headers(make_staff) -> Callable[[StaffRole], dict[str, str]]:
    def headers(role: StaffRole) -> dict[str, str]:
        return auth_headers("staff", make_staff(role).id)

    return headers


@pytest.fixture
def make_product(db: Session) -> Callable[..., Product]:
    count = 0

    def make(price: str = "1000", on_hand: int = 10, *, is_active: bool = True) -> Product:
        nonlocal count
        count += 1
        product = Product(
            sku=f"TEST-{count}",
            slug=f"test-product-{count}",
            name=f"Test product {count}",
            price=Decimal(price),
            is_active=is_active,
            inventory=Inventory(on_hand=on_hand),
        )
        db.add(product)
        db.flush()
        return product

    return make


@pytest.fixture
def make_customer(db: Session) -> Callable[..., Customer]:
    count = 0

    def make() -> Customer:
        nonlocal count
        count += 1
        customer = Customer(
            email=f"customer{count}@example.com",
            password_hash=hash_password("customer-password"),
            full_name=f"Customer {count}",
        )
        db.add(customer)
        db.flush()
        return customer

    return make


@pytest.fixture
def place_order(client, db, make_product):
    """Check out a guest cart and (by default) pay for it. Returns the order."""
    from tests.test_checkout import DETAILS
    from tests.test_payments import notify

    def place(*products_and_quantities, paid=True, gift_message="") -> Order:
        if not products_and_quantities:
            products_and_quantities = ((make_product(price="1200", on_hand=5), 2),)
        cart = {"X-Cart-Token": client.post("/cart").json()["token"]}
        for product, quantity in products_and_quantities:
            client.put(f"/cart/items/{product.id}", json={"quantity": quantity}, headers=cart)
        if gift_message:
            client.patch(
                "/cart", json={"gift_wrap": True, "gift_message": gift_message}, headers=cart
            )
        number = client.post("/checkout", json=DETAILS, headers=cart).json()["order_number"]
        order = db.scalar(select(Order).where(Order.order_number == number))
        if paid:
            notify(client, order)
        return order

    return place
