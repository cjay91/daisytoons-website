from datetime import UTC, date, datetime, timedelta

import pytest

from app.models import StaffRole, StockReason
from tests.test_fulfilment import post, stock_log

ADMIN, PACKER = StaffRole.ADMIN, StaffRole.PACKER


@pytest.fixture
def admin(staff_headers):
    return staff_headers(ADMIN)


@pytest.fixture
def supplier(client, admin):
    response = client.post(
        "/staff/suppliers",
        json={"name": "Lanka Crafts", "email": "sales@lankacrafts.lk", "phone": "0112345678"},
        headers=admin,
    )
    assert response.status_code == 201
    return response.json()


def test_suppliers_can_be_added_and_changed(client, admin, supplier):
    changed = client.put(
        f"/staff/suppliers/{supplier['id']}",
        json={"name": "Lanka Crafts Ltd", "is_active": False},
        headers=admin,
    )

    assert changed.json()["name"] == "Lanka Crafts Ltd"
    assert client.get("/staff/suppliers", headers=admin).json()[0]["is_active"] is False


def test_only_admins_manage_purchasing(client, staff_headers):
    packer = staff_headers(PACKER)
    assert client.get("/staff/suppliers", headers=packer).status_code == 403
    assert client.post("/staff/suppliers", json={"name": "X"}, headers=packer).status_code == 403
    assert client.get("/staff/purchase-orders", headers=packer).status_code == 403


def test_purchase_order_from_draft_to_received_adds_stock(
    client, db, admin, supplier, make_product
):
    bear = make_product(on_hand=1)
    bear.inventory.reorder_point = 2
    card = make_product(on_hand=0)
    body = {
        "supplier_id": supplier["id"],
        "expected_at": str(date.today() + timedelta(days=7)),
        "items": [
            {"product_id": bear.id, "quantity": 12, "unit_cost": "450"},
            {"product_id": card.id, "quantity": 50, "unit_cost": "40.50"},
        ],
    }
    created = client.post("/staff/purchase-orders", json=body, headers=admin)
    assert created.status_code == 201
    po = created.json()
    assert po["status"] == "draft"
    assert po["total"] == "7425.00"
    assert po["items"][0]["product"]["sku"] == bear.sku

    edited = client.put(
        f"/staff/purchase-orders/{po['id']}",
        json={**body, "items": body["items"][:1]},
        headers=admin,
    ).json()
    assert len(edited["items"]) == 1

    sent = client.post(f"/staff/purchase-orders/{po['id']}/send", headers=admin).json()
    assert sent["status"] == "sent" and sent["sent_at"]
    low = client.get("/staff/stock/low", headers=admin).json()
    assert {(i["product_id"], i["on_order"]) for i in low} >= {(bear.id, 12)}
    assert (
        client.put(f"/staff/purchase-orders/{po['id']}", json=body, headers=admin).status_code
        == 409
    )

    received = client.post(f"/staff/purchase-orders/{po['id']}/receive", headers=admin).json()
    assert received["status"] == "received" and received["received_at"]
    assert bear.inventory.on_hand == 13
    assert stock_log(db, bear)[-1] == (StockReason.RECEIVED, 12)
    again = client.post(f"/staff/purchase-orders/{po['id']}/receive", headers=admin)
    assert again.status_code == 409


def test_purchase_order_checks(client, admin, supplier, make_product):
    bear = make_product()
    item = {"product_id": bear.id, "quantity": 1, "unit_cost": "1"}

    twice = {"supplier_id": supplier["id"], "items": [item, item]}
    missing = {"supplier_id": supplier["id"], "items": [{**item, "product_id": 999999}]}
    empty = {"supplier_id": supplier["id"], "items": []}

    assert client.post("/staff/purchase-orders", json=twice, headers=admin).status_code == 409
    assert client.post("/staff/purchase-orders", json=missing, headers=admin).status_code == 404
    assert client.post("/staff/purchase-orders", json=empty, headers=admin).status_code == 422


def test_cancelled_purchase_orders_cannot_be_received(client, admin, supplier, make_product):
    item = {"product_id": make_product().id, "quantity": 1, "unit_cost": "1"}
    po = client.post(
        "/staff/purchase-orders",
        json={"supplier_id": supplier["id"], "items": [item]},
        headers=admin,
    ).json()

    client.post(f"/staff/purchase-orders/{po['id']}/cancel", headers=admin)

    response = client.post(f"/staff/purchase-orders/{po['id']}/receive", headers=admin)
    assert response.status_code == 409
    listed = client.get("/staff/purchase-orders?status=cancelled", headers=admin).json()
    assert [p["id"] for p in listed] == [po["id"]]


def test_low_stock_lists_products_at_or_below_their_reorder_point(client, admin, make_product):
    low = make_product(on_hand=3)
    fine = make_product(on_hand=10)
    gone = make_product(on_hand=0, is_active=False)
    for product in (low, fine, gone):
        product.inventory.reorder_point = 3

    body = client.get("/staff/stock/low", headers=admin).json()

    ids = [i["product_id"] for i in body]
    assert low.id in ids and fine.id not in ids and gone.id not in ids


def test_staff_product_list_includes_inactive_products_and_stock(client, admin, make_product):
    hidden = make_product(on_hand=4, is_active=False)

    listed = client.get(f"/staff/products?q={hidden.sku}", headers=admin).json()
    one = client.get(f"/staff/products/{hidden.id}", headers=admin).json()

    assert [p["id"] for p in listed] == [hidden.id]
    assert one["inventory"]["on_hand"] == 4 and one["available"] == 4


def test_daily_report(client, db, admin, make_product, place_order):
    mug = make_product(price="1200", on_hand=10)
    bear = make_product(price="3000", on_hand=10)
    first = place_order((mug, 2))  # 2400 + 400 delivery
    place_order((bear, 1), (mug, 1))  # 4200 + 400
    place_order(paid=False)
    yesterday = place_order((bear, 1))
    yesterday.paid_at = datetime.now(UTC) - timedelta(days=1)
    db.flush()
    post(client, admin, first, "refunds", {"amount": "400", "reason": "Delivery was late"})

    report = client.get("/staff/reports/daily", headers=admin).json()

    assert report["orders"] == 2
    assert report["revenue"] == "7400.00"
    assert report["average_order"] == "3700.00"
    assert report["items_sold"] == 4
    assert report["refunds"] == "400.00"
    assert [(p["name"], p["quantity"]) for p in report["top_products"]] == [
        (mug.name, 3),
        (bear.name, 1),
    ]
    assert report["waiting_to_ship"] == 3
    assert len(report["last_14_days"]) == 14
    assert report["last_14_days"][-1]["revenue"] == "7400.00"
    assert report["last_14_days"][-2]["orders"] == 1

    earlier = client.get(
        f"/staff/reports/daily?day={report['last_14_days'][-2]['day']}", headers=admin
    )
    assert earlier.json()["orders"] == 1


def test_reports_are_for_admins(client, staff_headers):
    assert client.get("/staff/reports/daily", headers=staff_headers(PACKER)).status_code == 403
