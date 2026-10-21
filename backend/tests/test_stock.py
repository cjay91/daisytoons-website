"""The Part 3 stock rule: every change to stock on hand is logged."""

import pytest
from sqlalchemy import func, select

from app.models import Inventory, StaffRole, StockAdjustment
from tests.conftest import auth_headers

ADMIN, PACKER = StaffRole.ADMIN, StaffRole.PACKER
MUG = {"sku": "MUG-001", "slug": "daisy-mug", "name": "Daisy mug", "price": "1850.00"}


@pytest.fixture
def product_id(client, staff_headers):
    return client.post("/staff/products", json=MUG, headers=staff_headers(ADMIN)).json()["id"]


def adjust(client, headers, product_id, **body):
    return client.post(
        f"/staff/products/{product_id}/stock-adjustments", json=body, headers=headers
    )


def test_change_and_count_are_logged(client, make_staff, product_id):
    packer = make_staff(PACKER)
    headers = auth_headers("staff", packer.id)

    received = adjust(client, headers, product_id, reason="received", quantity_change=24).json()
    counted = adjust(client, headers, product_id, reason="count", new_on_hand=22, note="2 missing")

    assert received["on_hand_before"] == 0 and received["on_hand_after"] == 24
    assert counted.json()["quantity_change"] == -2
    log = client.get(f"/staff/products/{product_id}/stock-adjustments", headers=headers).json()
    assert [(e["reason"], e["quantity_change"], e["staff_id"]) for e in log] == [
        ("count", -2, packer.id),
        ("received", 24, packer.id),
    ]
    stock = client.get(f"/staff/products/{product_id}/inventory", headers=headers).json()
    assert stock["on_hand"] == 22


def test_stock_cannot_go_below_zero(client, staff_headers, product_id):
    response = adjust(
        client, staff_headers(ADMIN), product_id, reason="damaged", quantity_change=-1
    )

    assert response.status_code == 409


def test_stock_cannot_drop_below_reserved(client, db, staff_headers, product_id):
    headers = staff_headers(ADMIN)
    adjust(client, headers, product_id, reason="received", quantity_change=5)
    db.get(Inventory, product_id).reserved = 3
    db.flush()

    response = adjust(client, headers, product_id, reason="count", new_on_hand=2)

    assert response.status_code == 409
    assert "3 reserved" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    "body",
    [
        {"reason": "received"},
        {"reason": "received", "quantity_change": 1, "new_on_hand": 1},
        {"reason": "import", "new_on_hand": 5},
        {"reason": "lost", "quantity_change": -1},
    ],
)
def test_adjustment_needs_exactly_one_amount_and_a_valid_reason(
    client, staff_headers, product_id, body
):
    assert adjust(client, staff_headers(ADMIN), product_id, **body).status_code == 422


def test_zero_change_is_rejected(client, staff_headers, product_id):
    response = adjust(
        client, staff_headers(ADMIN), product_id, reason="correction", quantity_change=0
    )

    assert response.status_code == 409


def test_log_always_adds_up_to_stock_on_hand(client, db, staff_headers, product_id):
    headers = staff_headers(ADMIN)
    for body in [
        {"reason": "received", "quantity_change": 30},
        {"reason": "damaged", "quantity_change": -2},
        {"reason": "returned", "quantity_change": 1},
        {"reason": "count", "new_on_hand": 27},
    ]:
        assert adjust(client, headers, product_id, **body).status_code == 201

    logged = db.scalar(
        select(func.sum(StockAdjustment.quantity_change)).where(
            StockAdjustment.product_id == product_id
        )
    )
    assert logged == db.get(Inventory, product_id).on_hand == 27
