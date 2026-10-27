from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DB, CurrentStaff, Mailer
from app.models import OrderStatus
from app.schemas import (
    OrderCancel,
    OrderNumbers,
    PickListOut,
    RefundCreate,
    ShipmentCreate,
    StaffOrderListOut,
    StaffOrderOut,
)
from app.services import fulfilment

router = APIRouter(prefix="/staff", tags=["staff orders"])


@router.get("/orders")
def list_orders(
    db: DB,
    staff: CurrentStaff,
    status: OrderStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    needs_attention: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StaffOrderListOut:
    """Without filters: paid orders waiting to be packed or shipped, oldest first."""
    return fulfilment.list_orders(
        db,
        staff,
        status=status,
        q=q,
        needs_attention=needs_attention,
        limit=limit,
        offset=offset,
    )


@router.get("/couriers")
def list_couriers(staff: CurrentStaff) -> list[str]:
    return fulfilment.COURIERS


@router.post("/orders/pack")
def start_packing(db: DB, staff: CurrentStaff, body: OrderNumbers) -> list[str]:
    """Move paid orders to packing, several at once."""
    return fulfilment.start_packing(db, staff, body.order_numbers)


@router.get("/pick-list")
def pick_list(
    db: DB,
    staff: CurrentStaff,
    order: Annotated[list[str] | None, Query(max_length=100)] = None,
) -> PickListOut:
    """What to take off the shelves. By default for every order being packed."""
    return fulfilment.pick_list(db, staff, order)


@router.get("/orders/{order_number}")
def get_order(db: DB, staff: CurrentStaff, order_number: str) -> StaffOrderOut:
    return fulfilment.order_out(db, staff, fulfilment.get_order(db, staff, order_number))


@router.post("/orders/{order_number}/pack")
def pack_order(db: DB, staff: CurrentStaff, order_number: str) -> StaffOrderOut:
    fulfilment.start_packing(db, staff, [order_number])
    return get_order(db, staff, order_number)


@router.post("/orders/{order_number}/ship")
def ship_order(
    db: DB, mailer: Mailer, staff: CurrentStaff, order_number: str, body: ShipmentCreate
) -> StaffOrderOut:
    order = fulfilment.ship(db, mailer, staff, order_number, body)
    return fulfilment.order_out(db, staff, order)


@router.post("/orders/{order_number}/resend-tracking")
def resend_tracking(
    db: DB, mailer: Mailer, staff: CurrentStaff, order_number: str
) -> StaffOrderOut:
    order = fulfilment.resend_tracking(db, mailer, staff, order_number)
    return fulfilment.order_out(db, staff, order)


@router.post("/orders/{order_number}/deliver")
def deliver_order(db: DB, staff: CurrentStaff, order_number: str) -> StaffOrderOut:
    order = fulfilment.mark_delivered(db, staff, order_number)
    return fulfilment.order_out(db, staff, order)


@router.post("/orders/{order_number}/cancel")
def cancel_order(
    db: DB, staff: CurrentStaff, order_number: str, body: OrderCancel
) -> StaffOrderOut:
    order = fulfilment.cancel_order(db, staff, order_number, body)
    return fulfilment.order_out(db, staff, order)


@router.post("/orders/{order_number}/refunds")
def refund_order(
    db: DB, staff: CurrentStaff, order_number: str, body: RefundCreate
) -> StaffOrderOut:
    order = fulfilment.refund_order(db, staff, order_number, body)
    return fulfilment.order_out(db, staff, order)


@router.post("/orders/{order_number}/resolve-attention")
def resolve_attention(db: DB, staff: CurrentStaff, order_number: str) -> StaffOrderOut:
    order = fulfilment.resolve_attention(db, staff, order_number)
    return fulfilment.order_out(db, staff, order)
