"""Suppliers, purchase orders and the low-stock list that tells staff what to reorder.

A purchase order starts as a draft, is marked sent once it has gone to the supplier, and is
received when the goods arrive, which adds them to stock (logged as received).
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.errors import Conflict, NotFound
from app.models import (
    Inventory,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Staff,
    StockReason,
    Supplier,
)
from app.permissions import Permission, require
from app.schemas import LowStockOut, PurchaseOrderIn, SupplierIn
from app.services.inventory import add_stock, lock_inventories

P = PurchaseOrderStatus


# Suppliers


def list_suppliers(db: Session, actor: Staff) -> list[Supplier]:
    require(actor, Permission.MANAGE_PURCHASING, "Your role cannot view suppliers.")
    return list(db.scalars(select(Supplier).order_by(Supplier.is_active.desc(), Supplier.name)))


def _supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFound("Supplier not found.")
    return supplier


def create_supplier(db: Session, actor: Staff, data: SupplierIn) -> Supplier:
    require(actor, Permission.MANAGE_PURCHASING, "Your role cannot add suppliers.")
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    return supplier


def update_supplier(db: Session, actor: Staff, supplier_id: int, data: SupplierIn) -> Supplier:
    require(actor, Permission.MANAGE_PURCHASING, "Your role cannot change suppliers.")
    supplier = _supplier(db, supplier_id)
    for field, value in data.model_dump().items():
        setattr(supplier, field, value)
    db.commit()
    return supplier


# Purchase orders


def _po_query():
    return select(PurchaseOrder).options(
        selectinload(PurchaseOrder.supplier),
        selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.product),
    )


def list_purchase_orders(
    db: Session, actor: Staff, status: PurchaseOrderStatus | None = None
) -> list[PurchaseOrder]:
    require(actor, Permission.MANAGE_PURCHASING, "Your role cannot view purchase orders.")
    query = _po_query()
    if status is not None:
        query = query.where(PurchaseOrder.status == status)
    return list(db.scalars(query.order_by(PurchaseOrder.id.desc())))


def get_purchase_order(db: Session, actor: Staff, po_id: int, *, lock=False) -> PurchaseOrder:
    require(actor, Permission.MANAGE_PURCHASING, "Your role cannot view purchase orders.")
    query = _po_query().where(PurchaseOrder.id == po_id)
    if lock:
        query = query.with_for_update(of=PurchaseOrder).execution_options(populate_existing=True)
    po = db.scalar(query)
    if po is None:
        raise NotFound("Purchase order not found.")
    return po


def _items(db: Session, data: PurchaseOrderIn) -> list[PurchaseOrderItem]:
    product_ids = [item.product_id for item in data.items]
    if len(set(product_ids)) != len(product_ids):
        raise Conflict("Each product can only be on a purchase order once.")
    found = set(db.scalars(select(Product.id).where(Product.id.in_(product_ids))))
    if missing := set(product_ids) - found:
        raise NotFound(f"Product {min(missing)} not found.")
    return [PurchaseOrderItem(**item.model_dump()) for item in data.items]


def create_purchase_order(db: Session, actor: Staff, data: PurchaseOrderIn) -> PurchaseOrder:
    require(actor, Permission.MANAGE_PURCHASING, "Your role cannot create purchase orders.")
    supplier = _supplier(db, data.supplier_id)
    if not supplier.is_active:
        raise Conflict(f"{supplier.name} is marked inactive.")
    po = PurchaseOrder(
        supplier_id=supplier.id,
        expected_at=data.expected_at,
        notes=data.notes,
        items=_items(db, data),
    )
    db.add(po)
    db.commit()
    return get_purchase_order(db, actor, po.id)


def update_purchase_order(
    db: Session, actor: Staff, po_id: int, data: PurchaseOrderIn
) -> PurchaseOrder:
    """Only drafts can be changed. The items are replaced."""
    po = get_purchase_order(db, actor, po_id, lock=True)
    if po.status != P.DRAFT:
        raise Conflict(f"This purchase order is {po.status}, so it can't be changed.")
    _supplier(db, data.supplier_id)
    po.supplier_id = data.supplier_id
    po.expected_at = data.expected_at
    po.notes = data.notes
    po.items.clear()
    db.flush()
    po.items.extend(_items(db, data))
    db.commit()
    return get_purchase_order(db, actor, po.id)


def send_purchase_order(db: Session, actor: Staff, po_id: int) -> PurchaseOrder:
    po = get_purchase_order(db, actor, po_id, lock=True)
    if po.status != P.DRAFT:
        raise Conflict(f"This purchase order is {po.status}, so it can't be sent.")
    po.status = P.SENT
    po.sent_at = datetime.now(UTC)
    db.commit()
    return get_purchase_order(db, actor, po.id)


def receive_purchase_order(db: Session, actor: Staff, po_id: int) -> PurchaseOrder:
    """The goods arrived: add every item to stock."""
    require(actor, Permission.MANAGE_STOCK, "Your role cannot change stock.")
    po = get_purchase_order(db, actor, po_id, lock=True)
    if po.status not in (P.DRAFT, P.SENT):
        raise Conflict(f"This purchase order is {po.status}, so it can't be received.")
    inventories = lock_inventories(db, [item.product_id for item in po.items])
    for item in po.items:
        inventory = inventories.get(item.product_id)
        if inventory is None:
            inventory = Inventory(product_id=item.product_id, on_hand=0, reserved=0)
            db.add(inventory)
            db.flush()
        add_stock(
            db, inventory, actor, item.quantity, StockReason.RECEIVED, f"Purchase order {po.id}"
        )
    po.status = P.RECEIVED
    po.received_at = datetime.now(UTC)
    db.commit()
    return get_purchase_order(db, actor, po.id)


def cancel_purchase_order(db: Session, actor: Staff, po_id: int) -> PurchaseOrder:
    po = get_purchase_order(db, actor, po_id, lock=True)
    if po.status not in (P.DRAFT, P.SENT):
        raise Conflict(f"This purchase order is {po.status}, so it can't be cancelled.")
    po.status = P.CANCELLED
    db.commit()
    return get_purchase_order(db, actor, po.id)


# Low stock


def on_order(db: Session) -> dict[int, int]:
    """Quantities on purchase orders that have been sent but not received, per product."""
    rows = db.execute(
        select(PurchaseOrderItem.product_id, func.sum(PurchaseOrderItem.quantity))
        .join(PurchaseOrder)
        .where(PurchaseOrder.status == P.SENT)
        .group_by(PurchaseOrderItem.product_id)
    )
    return {product_id: int(quantity) for product_id, quantity in rows}


def low_stock_query():
    """Products still sold whose available stock is at or below their reorder point."""
    return (
        select(Product, Inventory)
        .join(Inventory)
        .where(
            Product.is_active,
            Inventory.on_hand - Inventory.reserved <= Inventory.reorder_point,
        )
    )


def low_stock(db: Session, actor: Staff) -> list[LowStockOut]:
    require(actor, Permission.VIEW_CATALOG, "Your role cannot view stock.")
    ordered = on_order(db)
    rows = db.execute(
        low_stock_query().order_by(
            (Inventory.on_hand - Inventory.reserved - Inventory.reorder_point), Product.name
        )
    )
    return [
        LowStockOut(
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            is_active=product.is_active,
            on_hand=inventory.on_hand,
            reserved=inventory.reserved,
            available=max(inventory.on_hand - inventory.reserved, 0),
            reorder_point=inventory.reorder_point,
            bin_location=inventory.bin_location,
            on_order=ordered.get(product.id, 0),
        )
        for product, inventory in rows
    ]
