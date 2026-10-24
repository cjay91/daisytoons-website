from sqlalchemy import select

from app.models import Order, Tag, TagKind
from tests.conftest import auth_headers
from tests.test_checkout import DETAILS


def names(response) -> list[str]:
    return [p["name"] for p in response.json()]


def test_keyword_search_matches_name_description_and_tags(client, db, make_product):
    bear = make_product(price="2500")
    bear.name, bear.description = "Teddy bear", "Soft and huggable"
    mug = make_product(price="1200")
    mug.name = "Daisy mug"
    mug.tags = [db.scalar(select(Tag).where(Tag.kind == TagKind.OCCASION, Tag.slug == "birthday"))]
    db.flush()

    assert names(client.get("/products", params={"q": "teddy"})) == ["Teddy bear"]
    assert names(client.get("/products", params={"q": "HUGGABLE bear"})) == ["Teddy bear"]
    assert names(client.get("/products", params={"q": "birthday"})) == ["Daisy mug"]
    assert names(client.get("/products", params={"q": "teddy mug"})) == []
    # Wildcards typed by a shopper are plain text.
    assert names(client.get("/products", params={"q": "%"})) == []


def test_price_range_and_sort(client, make_product):
    for price in ("500", "1500", "3000"):
        make_product(price=price)

    response = client.get("/products", params={"min_price": 1000, "max_price": 3000})
    assert [p["price"] for p in response.json()] == ["1500.00", "3000.00"]

    response = client.get("/products", params={"sort": "price_desc"})
    assert [p["price"] for p in response.json()] == ["3000.00", "1500.00", "500.00"]
    assert client.get("/products", params={"sort": "random"}).status_code == 422


def test_products_show_available_stock(client, db, make_product):
    mug = make_product(on_hand=5)
    mug.inventory.reserved = 2
    db.flush()

    listed = client.get("/products").json()[0]
    assert listed["available"] == 3
    assert "inventory" not in listed
    assert client.get(f"/products/{mug.slug}").json()["available"] == 3


def place_order(client, customer, product):
    login = auth_headers("customer", customer.id)
    client.put(f"/cart/items/{product.id}", json={"quantity": 2}, headers=login)
    return client.post("/checkout", json=DETAILS, headers=login).json()["order_number"]


def test_customer_sees_only_their_own_orders(client, db, make_product, make_customer):
    alice, bob = make_customer(), make_customer()
    number = place_order(client, alice, make_product(price="1000"))

    orders = client.get("/me/orders", headers=auth_headers("customer", alice.id)).json()
    assert [(o["order_number"], o["item_count"], o["status"]) for o in orders] == [
        (number, 2, "pending")
    ]
    assert client.get("/me/orders", headers=auth_headers("customer", bob.id)).json() == []

    detail = client.get(f"/me/orders/{number}", headers=auth_headers("customer", alice.id))
    assert detail.status_code == 200
    body = detail.json()
    assert [e["to_status"] for e in body["events"]] == ["pending"]
    order = db.scalar(select(Order).where(Order.order_number == number))
    assert body["access_key"] == order.access_key

    other = client.get(f"/me/orders/{number}", headers=auth_headers("customer", bob.id))
    assert other.status_code == 404
    assert client.get("/me/orders").status_code == 401


ADDRESS = {
    "recipient_name": "Nimali Perera",
    "line1": "12 Flower Road",
    "city": "Colombo 7",
    "district": "Colombo",
}


def test_addresses_first_is_default_and_one_default_at_a_time(client, make_customer):
    headers = auth_headers("customer", make_customer().id)

    home = client.post("/me/addresses", json=ADDRESS, headers=headers).json()
    assert home["is_default"] is True
    assert home["district"] == "Colombo"
    office = client.post(
        "/me/addresses", json={**ADDRESS, "label": "Office", "is_default": True}, headers=headers
    ).json()

    listed = client.get("/me/addresses", headers=headers).json()
    assert [(a["id"], a["is_default"]) for a in listed] == [
        (office["id"], True),
        (home["id"], False),
    ]

    changed = client.put(
        f"/me/addresses/{home['id']}",
        json={**ADDRESS, "city": "Kandy", "district": "Kandy"},
        headers=headers,
    )
    assert changed.json()["city"] == "Kandy"

    assert client.delete(f"/me/addresses/{office['id']}", headers=headers).status_code == 204
    listed = client.get("/me/addresses", headers=headers).json()
    assert [(a["id"], a["is_default"]) for a in listed] == [(home["id"], True)]


def test_addresses_are_private_and_validated(client, make_customer):
    alice = auth_headers("customer", make_customer().id)
    bob = auth_headers("customer", make_customer().id)
    address = client.post("/me/addresses", json=ADDRESS, headers=alice).json()

    assert client.delete(f"/me/addresses/{address['id']}", headers=bob).status_code == 404
    assert (
        client.put(f"/me/addresses/{address['id']}", json=ADDRESS, headers=bob).status_code == 404
    )
    bad = client.post("/me/addresses", json={**ADDRESS, "district": "Atlantis"}, headers=alice)
    assert bad.status_code == 422
