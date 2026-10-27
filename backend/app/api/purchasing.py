from datetime import date

from fastapi import APIRouter, status

from app.api.deps import DB, CurrentStaff
from app.models import PurchaseOrderStatus
from app.schemas import (
    DailyReportOut,
    LowStockOut,
    PurchaseOrderIn,
    PurchaseOrderOut,
    SupplierIn,
    SupplierOut,
)
from app.services import purchasing, reports

router = APIRouter(prefix="/staff", tags=["staff purchasing"])


@router.get("/stock/low")
def low_stock(db: DB, staff: CurrentStaff) -> list[LowStockOut]:
    """Products to reorder: available stock at or below the reorder point."""
    return purchasing.low_stock(db, staff)


@router.get("/suppliers")
def list_suppliers(db: DB, staff: CurrentStaff) -> list[SupplierOut]:
    return [SupplierOut.model_validate(s) for s in purchasing.list_suppliers(db, staff)]


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(db: DB, staff: CurrentStaff, body: SupplierIn) -> SupplierOut:
    return SupplierOut.model_validate(purchasing.create_supplier(db, staff, body))


@router.put("/suppliers/{supplier_id}")
def update_supplier(db: DB, staff: CurrentStaff, supplier_id: int, body: SupplierIn) -> SupplierOut:
    return SupplierOut.model_validate(purchasing.update_supplier(db, staff, supplier_id, body))


@router.get("/purchase-orders")
def list_purchase_orders(
    db: DB, staff: CurrentStaff, status: PurchaseOrderStatus | None = None
) -> list[PurchaseOrderOut]:
    return [
        PurchaseOrderOut.model_validate(po)
        for po in purchasing.list_purchase_orders(db, staff, status)
    ]


@router.post("/purchase-orders", status_code=status.HTTP_201_CREATED)
def create_purchase_order(db: DB, staff: CurrentStaff, body: PurchaseOrderIn) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(purchasing.create_purchase_order(db, staff, body))


@router.get("/purchase-orders/{po_id}")
def get_purchase_order(db: DB, staff: CurrentStaff, po_id: int) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(purchasing.get_purchase_order(db, staff, po_id))


@router.put("/purchase-orders/{po_id}")
def update_purchase_order(
    db: DB, staff: CurrentStaff, po_id: int, body: PurchaseOrderIn
) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(purchasing.update_purchase_order(db, staff, po_id, body))


@router.post("/purchase-orders/{po_id}/send")
def send_purchase_order(db: DB, staff: CurrentStaff, po_id: int) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(purchasing.send_purchase_order(db, staff, po_id))


@router.post("/purchase-orders/{po_id}/receive")
def receive_purchase_order(db: DB, staff: CurrentStaff, po_id: int) -> PurchaseOrderOut:
    """The goods arrived: adds every item to stock."""
    return PurchaseOrderOut.model_validate(purchasing.receive_purchase_order(db, staff, po_id))


@router.post("/purchase-orders/{po_id}/cancel")
def cancel_purchase_order(db: DB, staff: CurrentStaff, po_id: int) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(purchasing.cancel_purchase_order(db, staff, po_id))


@router.get("/reports/daily")
def daily_report(db: DB, staff: CurrentStaff, day: date | None = None) -> DailyReportOut:
    """Sales for one day (today by default, Sri Lanka time) and the 14 days up to it."""
    return reports.daily_report(db, staff, day)
