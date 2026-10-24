from tests.conftest import auth_headers


def new_cart(client) -> dict[str, str]:
    token = client.post("/cart").json()["token"]
    return {"X-Cart-Token": token}


def test_guest_cart_add_change_remove(client, make_product):
    mug = make_product(price="1200")
    headers = new_cart(client)

    cart = client.put(f"/cart/items/{mug.id}", json={"quantity": 2}, headers=headers).json()
    assert cart["items"][0]["quantity"] == 2
    assert cart["subtotal"] == "2400.00"
    assert cart["item_count"] == 2

    cart = client.put(f"/cart/items/{mug.id}", json={"quantity": 3}, headers=headers).json()
    assert cart["subtotal"] == "3600.00"

    cart = client.put(f"/cart/items/{mug.id}", json={"quantity": 0}, headers=headers).json()
    assert cart["items"] == []
    assert client.get("/cart", headers=headers).json()["items"] == []


def test_no_cart_yet_reads_as_empty(client):
    cart = client.get("/cart").json()
    assert cart["token"] is None
    assert cart["items"] == []


def test_cart_shows_delivery_and_gift_wrap_fees(client, make_product):
    bear = make_product(price="2500")
    headers = new_cart(client)
    client.put(f"/cart/items/{bear.id}", json={"quantity": 1}, headers=headers)

    cart = client.patch(
        "/cart", json={"gift_wrap": True, "gift_message": " Happy birthday! "}, headers=headers
    ).json()

    assert cart["gift_wrap_fee"] == "250.00"
    assert cart["gift_message"] == "Happy birthday!"
    assert cart["delivery_fee_colombo"] == "400.00"
    assert cart["delivery_fee_other"] == "650.00"
    assert cart["currency"] == "LKR"

    client.put(f"/cart/items/{bear.id}", json={"quantity": 4}, headers=headers)
    cart = client.get("/cart", headers=headers).json()
    assert cart["subtotal"] == "10000.00"
    assert cart["delivery_fee_colombo"] == "0.00"
    assert cart["delivery_fee_other"] == "0.00"


def test_cannot_add_more_than_available(client, db, make_product):
    mug = make_product(on_hand=3)
    mug.inventory.reserved = 1
    db.flush()
    headers = new_cart(client)

    response = client.put(f"/cart/items/{mug.id}", json={"quantity": 3}, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["message"] == f"Only 2 of {mug.name} left in stock."

    assert client.put(f"/cart/items/{mug.id}", json={"quantity": 2}, headers=headers).is_success


def test_lowering_a_quantity_is_allowed_after_stock_runs_short(client, db, make_product):
    mug = make_product(on_hand=5)
    headers = new_cart(client)
    client.put(f"/cart/items/{mug.id}", json={"quantity": 5}, headers=headers)
    mug.inventory.on_hand = 1
    db.flush()

    response = client.put(f"/cart/items/{mug.id}", json={"quantity": 4}, headers=headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["available"] == 1


def test_inactive_or_missing_products_cannot_be_added(client, make_product):
    hidden = make_product(is_active=False)
    headers = new_cart(client)

    assert (
        client.put(f"/cart/items/{hidden.id}", json={"quantity": 1}, headers=headers).status_code
        == 404
    )
    assert (
        client.put("/cart/items/999999", json={"quantity": 1}, headers=headers).status_code == 404
    )


def test_at_most_twenty_of_one_product(client, make_product):
    mug = make_product(on_hand=100)
    headers = new_cart(client)

    response = client.put(f"/cart/items/{mug.id}", json={"quantity": 21}, headers=headers)
    assert response.status_code == 422


def test_guest_cart_merges_into_customer_cart_on_login(client, make_product, make_customer):
    mug, bear = make_product(), make_product()
    customer = make_customer()
    login = auth_headers("customer", customer.id)

    client.put(f"/cart/items/{mug.id}", json={"quantity": 1}, headers=login)
    guest = new_cart(client)
    client.put(f"/cart/items/{mug.id}", json={"quantity": 2}, headers=guest)
    client.put(f"/cart/items/{bear.id}", json={"quantity": 1}, headers=guest)

    cart = client.get("/cart", headers={**login, **guest}).json()
    quantities = {item["product_id"]: item["quantity"] for item in cart["items"]}
    assert quantities == {mug.id: 3, bear.id: 1}

    # The guest cart is gone; the customer's cart stays.
    assert client.get("/cart", headers=guest).json()["items"] == []
    assert len(client.get("/cart", headers=login).json()["items"]) == 2


def test_guest_cart_becomes_the_customers_cart_when_they_have_none(
    client, make_product, make_customer
):
    mug = make_product()
    login = auth_headers("customer", make_customer().id)
    guest = new_cart(client)
    client.put(f"/cart/items/{mug.id}", json={"quantity": 2}, headers=guest)

    cart = client.get("/cart", headers={**login, **guest}).json()
    assert cart["items"][0]["quantity"] == 2
    assert client.get("/cart", headers=login).json()["item_count"] == 2


def test_expired_login_is_an_error_not_a_guest(client):
    response = client.get("/cart", headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401
