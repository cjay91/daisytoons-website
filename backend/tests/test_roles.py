"""Role checks from the Part 2 spec. The headline rule: a packer cannot change prices."""

import pytest

from app.errors import Forbidden
from app.models import StaffRole
from app.schemas import ProductCreate, ProductUpdate
from app.services import products

ADMIN, PACKER, SUPPORT = StaffRole.ADMIN, StaffRole.PACKER, StaffRole.SUPPORT
NEW_PRODUCT = {"sku": "MUG-001", "slug": "daisy-mug", "name": "Daisy mug", "price": "12.50"}


@pytest.fixture
def product_id(client, staff_headers):
    response = client.post("/staff/products", json=NEW_PRODUCT, headers=staff_headers(ADMIN))
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize(("role", "status"), [(ADMIN, 201), (PACKER, 403), (SUPPORT, 403)])
def test_create_product(client, staff_headers, role, status):
    response = client.post("/staff/products", json=NEW_PRODUCT, headers=staff_headers(role))

    assert response.status_code == status


@pytest.mark.parametrize(("role", "status"), [(ADMIN, 200), (PACKER, 403), (SUPPORT, 403)])
def test_change_price(client, staff_headers, product_id, role, status):
    response = client.patch(
        f"/staff/products/{product_id}", json={"price": "9.99"}, headers=staff_headers(role)
    )

    assert response.status_code == status


def test_packer_is_told_they_cannot_change_prices(client, staff_headers, product_id):
    response = client.patch(
        f"/staff/products/{product_id}", json={"price": "0.01"}, headers=staff_headers(PACKER)
    )

    assert response.json() == {
        "error": {"code": "forbidden", "message": "Your role cannot change prices."}
    }
    price = client.get("/products/daisy-mug").json()["price"]
    assert price == "12.50"


def test_packer_cannot_change_prices_through_the_service_either(db, make_staff):
    """Agents and the console call services directly, so the rule must hold there too."""
    admin, packer = make_staff(ADMIN), make_staff(PACKER)
    product = products.create_product(db, admin, ProductCreate(**NEW_PRODUCT))

    with pytest.raises(Forbidden):
        products.update_product(db, packer, product.id, ProductUpdate(price="0.01"))


@pytest.mark.parametrize(("role", "status"), [(ADMIN, 201), (PACKER, 201), (SUPPORT, 403)])
def test_change_stock(client, staff_headers, product_id, role, status):
    response = client.post(
        f"/staff/products/{product_id}/stock-adjustments",
        json={"reason": "received", "quantity_change": 20},
        headers=staff_headers(role),
    )

    assert response.status_code == status


@pytest.mark.parametrize(("role", "status"), [(ADMIN, 200), (PACKER, 200), (SUPPORT, 403)])
def test_change_bin_location(client, staff_headers, product_id, role, status):
    response = client.patch(
        f"/staff/products/{product_id}/inventory",
        json={"bin_location": "A-3"},
        headers=staff_headers(role),
    )

    assert response.status_code == status


@pytest.mark.parametrize(("role", "status"), [(ADMIN, 200), (PACKER, 200), (SUPPORT, 200)])
def test_view_stock_log(client, staff_headers, product_id, role, status):
    response = client.get(
        f"/staff/products/{product_id}/stock-adjustments", headers=staff_headers(role)
    )

    assert response.status_code == status


@pytest.mark.parametrize(("role", "status"), [(ADMIN, 201), (PACKER, 403), (SUPPORT, 403)])
def test_add_tag(client, staff_headers, role, status):
    response = client.post(
        "/staff/tags", json={"kind": "occasion", "name": "Poya"}, headers=staff_headers(role)
    )

    assert response.status_code == status


@pytest.mark.parametrize(("role", "status"), [(ADMIN, 200), (PACKER, 403), (SUPPORT, 403)])
def test_set_product_tags(client, staff_headers, product_id, role, status):
    response = client.put(
        f"/staff/products/{product_id}/tags",
        json={"occasions": ["birthday"]},
        headers=staff_headers(role),
    )

    assert response.status_code == status


@pytest.mark.parametrize("role", [ADMIN, PACKER, SUPPORT])
def test_every_role_can_view_stock(client, staff_headers, product_id, role):
    response = client.get(f"/staff/products/{product_id}/inventory", headers=staff_headers(role))

    assert response.status_code == 200


@pytest.mark.parametrize(("role", "status"), [(ADMIN, 201), (PACKER, 403), (SUPPORT, 403)])
def test_add_staff_member(client, staff_headers, role, status):
    response = client.post(
        "/staff/members",
        json={
            "email": "new@example.com",
            "password": "new-staff-password",
            "full_name": "New",
            "role": "support",
        },
        headers=staff_headers(role),
    )

    assert response.status_code == status


@pytest.mark.parametrize(("role", "status"), [(ADMIN, 200), (PACKER, 403), (SUPPORT, 403)])
def test_list_staff_members(client, staff_headers, role, status):
    assert client.get("/staff/members", headers=staff_headers(role)).status_code == status


def test_staff_endpoints_need_a_staff_login(client):
    assert client.post("/staff/products", json=NEW_PRODUCT).status_code == 401
