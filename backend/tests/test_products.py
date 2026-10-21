from app.models import Inventory, StaffRole

ADMIN = StaffRole.ADMIN
MUG = {"sku": "MUG-001", "slug": "daisy-mug", "name": "Daisy mug", "price": "12.50"}


def create(client, headers, **overrides):
    return client.post("/staff/products", json={**MUG, **overrides}, headers=headers)


def test_public_list_shows_only_active_products(client, staff_headers):
    headers = staff_headers(ADMIN)
    create(client, headers)
    create(client, headers, sku="OLD-1", slug="old-card", name="Old card", is_active=False)

    names = [p["name"] for p in client.get("/products").json()]

    assert names == ["Daisy mug"]
    assert client.get("/products/old-card").status_code == 404


def test_prices_are_in_sri_lankan_rupees(client, staff_headers):
    created = create(client, staff_headers(ADMIN), price="1250.00").json()

    assert created["price"] == "1250.00"
    assert created["currency"] == "LKR"


def test_new_product_starts_with_empty_stock(client, staff_headers):
    headers = staff_headers(ADMIN)
    product_id = create(client, headers).json()["id"]

    stock = client.get(f"/staff/products/{product_id}/inventory", headers=headers).json()

    assert stock == {
        "product_id": product_id,
        "on_hand": 0,
        "reserved": 0,
        "reorder_point": 0,
        "bin_location": None,
    }


def test_duplicate_sku_or_slug_is_a_conflict(client, staff_headers):
    headers = staff_headers(ADMIN)
    create(client, headers)

    assert create(client, headers, slug="other").status_code == 409
    assert create(client, headers, sku="OTHER").status_code == 409


def test_negative_price_is_rejected(client, staff_headers):
    response = create(client, staff_headers(ADMIN), price="-1")

    assert response.status_code == 422


def test_stock_cannot_drop_below_reserved(client, db, staff_headers):
    headers = staff_headers(ADMIN)
    product_id = create(client, headers).json()["id"]
    client.patch(f"/staff/products/{product_id}/inventory", json={"on_hand": 5}, headers=headers)

    db.get(Inventory, product_id).reserved = 3
    db.flush()

    response = client.patch(
        f"/staff/products/{product_id}/inventory", json={"on_hand": 2}, headers=headers
    )

    assert response.status_code == 409


def test_unknown_product_is_not_found(client, staff_headers):
    response = client.patch(
        "/staff/products/999999", json={"name": "Nope"}, headers=staff_headers(ADMIN)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
