from decimal import Decimal

import pytest
from sqlalchemy import select

from app import payhere
from app.config import get_settings
from app.models import Order, OrderStatus
from tests.conftest import auth_headers

ADDRESS = {"line1": "12 Flower Road", "city": "Colombo 7", "district": "Colombo"}
DETAILS = {
    "email": "guest@example.com",
    "customer_name": "Nimali Perera",
    "phone": "0771234567",
    "address": ADDRESS,
}


@pytest.fixture
def cart(client):
    return {"X-Cart-Token": client.post("/cart").json()["token"]}


def add(client, cart, product, quantity):
    response = client.put(f"/cart/items/{product.id}", json={"quantity": quantity}, headers=cart)
    assert response.is_success, response.json()


def test_checkout_creates_a_pending_order_and_reserves_stock(client, db, cart, make_product):
    mug = make_product(price="1200", on_hand=5)
    add(client, cart, mug, 2)

    response = client.post("/checkout", json=DETAILS, headers=cart)

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["order_number"].startswith("DT-") and len(body["order_number"]) == 9
    assert body["total"] == "2800.00"  # 2400 goods + 400 Colombo delivery
    assert body["currency"] == "LKR"
    order = db.scalar(select(Order).where(Order.order_number == body["order_number"]))
    assert order.status == OrderStatus.PENDING
    assert order.items[0].product_name == mug.name
    assert order.items[0].unit_price == mug.price
    assert order.shipping_address["district"] == "Colombo"
    assert [e.to_status for e in order.events] == [OrderStatus.PENDING]
    assert mug.inventory.reserved == 2
    assert mug.inventory.on_hand == 5


def test_totals_with_gift_wrap_outside_colombo(client, cart, make_product):
    bear = make_product(price="2000")
    add(client, cart, bear, 1)
    client.patch("/cart", json={"gift_wrap": True, "gift_message": "For you"}, headers=cart)

    details = {**DETAILS, "address": {**ADDRESS, "district": "Kandy"}}
    body = client.post("/checkout", json=details, headers=cart).json()

    assert body["total"] == "2900.00"  # 2000 + 250 wrap + 650 delivery


def test_free_delivery_over_the_threshold(client, cart, make_product):
    bear = make_product(price="5000")
    add(client, cart, bear, 2)

    assert client.post("/checkout", json=DETAILS, headers=cart).json()["total"] == "10000.00"


def test_payment_form_for_payhere(client, cart, make_product, monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "payhere")
    get_settings.cache_clear()
    try:
        mug = make_product(price="1200")
        add(client, cart, mug, 1)
        body = client.post("/checkout", json=DETAILS, headers=cart).json()
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    form = body["payment"]
    assert form["action_url"] == payhere.SANDBOX_CHECKOUT_URL
    fields = form["fields"]
    assert fields["order_id"] == body["order_number"]
    assert fields["amount"] == "1600.00"
    assert fields["currency"] == "LKR"
    assert fields["notify_url"].endswith("/payments/payhere/notify")
    assert body["order_key"] in fields["return_url"]
    assert fields["hash"] == payhere.checkout_hash(
        settings, body["order_number"], Decimal("1600"), "LKR"
    )


def test_fake_gateway_is_used_by_default(client, cart, make_product):
    add(client, cart, make_product(), 1)
    body = client.post("/checkout", json=DETAILS, headers=cart).json()
    assert body["payment"]["action_url"].endswith("/payments/fake/checkout")


def test_empty_cart_cannot_check_out(client, cart):
    response = client.post("/checkout", json=DETAILS, headers=cart)
    assert response.status_code == 409
    assert client.post("/checkout", json=DETAILS).status_code == 409


def test_unknown_district_is_refused(client, cart, make_product):
    add(client, cart, make_product(), 1)
    details = {**DETAILS, "address": {**ADDRESS, "district": "Atlantis"}}
    assert client.post("/checkout", json=details, headers=cart).status_code == 422


def test_guest_needs_an_email(client, cart, make_product):
    add(client, cart, make_product(), 1)
    details = {k: v for k, v in DETAILS.items() if k != "email"}
    assert client.post("/checkout", json=details, headers=cart).status_code == 409


def test_customer_email_is_used_when_left_out(client, db, make_product, make_customer):
    customer = make_customer()
    login = auth_headers("customer", customer.id)
    add(client, login, make_product(), 1)
    details = {k: v for k, v in DETAILS.items() if k != "email"}

    number = client.post("/checkout", json=details, headers=login).json()["order_number"]

    order = db.scalar(select(Order).where(Order.order_number == number))
    assert order.email == customer.email
    assert order.customer_id == customer.id


def test_stock_sold_out_since_adding_is_refused(client, db, cart, make_product):
    mug = make_product(on_hand=2)
    add(client, cart, mug, 2)
    mug.inventory.on_hand = 1
    db.flush()

    response = client.post("/checkout", json=DETAILS, headers=cart)

    assert response.status_code == 409
    assert "Only 1" in response.json()["error"]["message"]
    assert mug.inventory.reserved == 0
    assert db.scalar(select(Order)) is None


def test_product_taken_off_sale_is_refused(client, db, cart, make_product):
    mug = make_product()
    add(client, cart, mug, 1)
    mug.is_active = False
    db.flush()

    assert client.post("/checkout", json=DETAILS, headers=cart).status_code == 409


def test_checking_out_again_replaces_the_unpaid_order(client, db, cart, make_product):
    mug = make_product(on_hand=3)
    add(client, cart, mug, 3)

    first = client.post("/checkout", json=DETAILS, headers=cart).json()["order_number"]
    second = client.post("/checkout", json=DETAILS, headers=cart).json()["order_number"]

    orders = {o.order_number: o for o in db.scalars(select(Order))}
    assert orders[first].status == OrderStatus.CANCELLED
    assert orders[second].status == OrderStatus.PENDING
    assert mug.inventory.reserved == 3


def test_order_page_needs_the_key(client, cart, make_product):
    add(client, cart, make_product(), 1)
    body = client.post("/checkout", json=DETAILS, headers=cart).json()
    number = body["order_number"]

    page = client.get(f"/orders/{number}", params={"key": body["order_key"]})
    assert page.status_code == 200
    assert page.json()["status"] == "pending"
    assert page.json()["currency"] == "LKR"

    assert client.get(f"/orders/{number}", params={"key": "wrong"}).status_code == 404
    assert client.get("/orders/DT-NOPE00", params={"key": "x"}).status_code == 404


def test_districts_are_listed(client):
    districts = client.get("/checkout/districts").json()
    assert len(districts) == 25
    assert "Colombo" in districts
