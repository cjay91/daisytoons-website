"""Stock. On-hand quantities change only through adjust_stock, record_import_stock or
record_sale, which write the new number and its log entry together. Reserved quantities (held
for unpaid orders) change only through reserve_stock and release_stock."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import Conflict, NotFound
from app.models import Inventory, Staff, StockAdjustment, StockReason
from app.permissions import Permission, require
from app.schemas import InventoryUpdate, StockAdjustmentCreate


def lock_inventories(db: Session, product_ids: list[int]) -> dict[int, Inventory]:
    """Lock several stock rows, always in product id order so two orders can't deadlock."""
    rows = db.scalars(
        select(Inventory)
        .where(Inventory.product_id.in_(product_ids))
        .order_by(Inventory.product_id)
        .with_for_update()
        # Locked rows are read fresh, not from what this session loaded before.
        .execution_options(populate_existing=True)
    )
    return {row.product_id: row for row in rows}


def available(inventory: Inventory) -> int:
    return max(inventory.on_hand - inventory.reserved, 0)


def reserve_stock(inventory: Inventory, quantity: int) -> None:
    """Hold stock for an unpaid order. The caller has locked the row and checked availability."""
    if quantity > available(inventory):
        raise Conflict("Not enough stock to reserve.")
    inventory.reserved += quantity


def release_stock(inventory: Inventory, quantity: int) -> None:
    inventory.reserved = max(inventory.reserved - quantity, 0)


def record_sale(db: Session, inventory: Inventory, quantity: int, note: str) -> None:
    """A paid order: its reserved stock leaves the shelf. Does not commit."""
    release_stock(inventory, quantity)
    _apply(
        db,
        inventory,
        staff=None,
        reason=StockReason.SALE,
        new_on_hand=inventory.on_hand - quantity,
        note=note,
    )


def _locked_inventory(db: Session, product_id: int) -> Inventory:
    # FOR UPDATE: two staff adjusting the same product at once are applied one after the other.
    inventory = db.scalar(
        select(Inventory)
        .where(Inventory.product_id == product_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if inventory is None:
        raise NotFound("Product not found.")
    return inventory


def _apply(
    db: Session,
    inventory: Inventory,
    *,
    staff: Staff | None,
    reason: StockReason,
    new_on_hand: int,
    note: str,
) -> StockAdjustment:
    if new_on_hand < 0:
        raise Conflict("Stock on hand cannot go below zero.")
    if new_on_hand < inventory.reserved:
        raise Conflict(
            f"Stock on hand cannot be lower than the {inventory.reserved} reserved for orders."
        )
    adjustment = StockAdjustment(
        product_id=inventory.product_id,
        staff_id=staff.id if staff else None,
        reason=reason,
        quantity_change=new_on_hand - inventory.on_hand,
        on_hand_before=inventory.on_hand,
        on_hand_after=new_on_hand,
        note=note,
    )
    inventory.on_hand = new_on_hand
    db.add(adjustment)
    return adjustment


def adjust_stock(
    db: Session, actor: Staff, product_id: int, data: StockAdjustmentCreate
) -> StockAdjustment:
    require(actor, Permission.MANAGE_STOCK, "Your role cannot change stock.")
    inventory = _locked_inventory(db, product_id)
    if data.new_on_hand is not None:
        new_on_hand = data.new_on_hand
    else:
        if data.quantity_change == 0:
            raise Conflict("A stock change can't be zero. Use a count to confirm stock.")
        new_on_hand = inventory.on_hand + data.quantity_change
    adjustment = _apply(
        db, inventory, staff=actor, reason=data.reason, new_on_hand=new_on_hand, note=data.note
    )
    db.commit()
    return adjustment


def record_import_stock(db: Session, inventory: Inventory, new_on_hand: int) -> bool:
    """Used by the import script. Logs only real changes. Does not commit."""
    if inventory.on_hand == new_on_hand:
        return False
    _apply(
        db,
        inventory,
        staff=None,
        reason=StockReason.IMPORT,
        new_on_hand=new_on_hand,
        note="Product import",
    )
    return True


def list_adjustments(db: Session, actor: Staff, product_id: int) -> list[StockAdjustment]:
    require(actor, Permission.VIEW_CATALOG, "Your role cannot view stock.")
    if db.get(Inventory, product_id) is None:
        raise NotFound("Product not found.")
    return list(
        db.scalars(
            select(StockAdjustment)
            .where(StockAdjustment.product_id == product_id)
            .order_by(StockAdjustment.created_at.desc(), StockAdjustment.id.desc())
        )
    )


def get_inventory(db: Session, actor: Staff, product_id: int) -> Inventory:
    require(actor, Permission.VIEW_CATALOG, "Your role cannot view stock.")
    inventory = db.get(Inventory, product_id)
    if inventory is None:
        raise NotFound("Product not found.")
    return inventory


def update_inventory(
    db: Session, actor: Staff, product_id: int, data: InventoryUpdate
) -> Inventory:
    """Reorder point and bin location. Stock on hand goes through adjust_stock."""
    require(actor, Permission.MANAGE_STOCK, "Your role cannot change stock.")
    inventory = get_inventory(db, actor, product_id)
    changes = data.model_dump(exclude_none=True)
    if "bin_location" in changes:
        # An empty string clears the bin location.
        changes["bin_location"] = changes["bin_location"].strip() or None
    for field, value in changes.items():
        setattr(inventory, field, value)
    db.commit()
    return inventory
