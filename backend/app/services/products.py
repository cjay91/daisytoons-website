from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import Conflict, NotFound
from app.models import Inventory, Product, Staff
from app.permissions import Permission, require
from app.schemas import InventoryUpdate, ProductCreate, ProductUpdate


def list_active_products(db: Session) -> list[Product]:
    return list(db.scalars(select(Product).where(Product.is_active).order_by(Product.name)))


def get_active_product_by_slug(db: Session, slug: str) -> Product:
    product = db.scalar(select(Product).where(Product.slug == slug, Product.is_active))
    if product is None:
        raise NotFound("Product not found.")
    return product


def _get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("Product not found.")
    return product


def _ensure_unique(db: Session, *, sku: str | None, slug: str | None, exclude_id: int | None):
    if sku is not None:
        existing = db.scalar(select(Product.id).where(Product.sku == sku))
        if existing is not None and existing != exclude_id:
            raise Conflict("A product with this SKU already exists.")
    if slug is not None:
        existing = db.scalar(select(Product.id).where(Product.slug == slug))
        if existing is not None and existing != exclude_id:
            raise Conflict("A product with this slug already exists.")


def create_product(db: Session, actor: Staff, data: ProductCreate) -> Product:
    require(actor, Permission.MANAGE_PRODUCTS, "Your role cannot create products.")
    _ensure_unique(db, sku=data.sku, slug=data.slug, exclude_id=None)
    product = Product(**data.model_dump(), inventory=Inventory())
    db.add(product)
    db.commit()
    return product


def update_product(db: Session, actor: Staff, product_id: int, data: ProductUpdate) -> Product:
    changes = data.model_dump(exclude_none=True)
    message = (
        "Your role cannot change prices."
        if "price" in changes
        else "Your role cannot change products."
    )
    require(actor, Permission.MANAGE_PRODUCTS, message)
    product = _get_product(db, product_id)
    _ensure_unique(db, sku=None, slug=changes.get("slug"), exclude_id=product.id)
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    return product


def get_inventory(db: Session, actor: Staff, product_id: int) -> Inventory:
    require(actor, Permission.VIEW_CATALOG, "Your role cannot view stock.")
    return _get_product(db, product_id).inventory


def update_inventory(
    db: Session, actor: Staff, product_id: int, data: InventoryUpdate
) -> Inventory:
    require(actor, Permission.MANAGE_STOCK, "Your role cannot change stock.")
    inventory = _get_product(db, product_id).inventory
    changes = data.model_dump(exclude_none=True)
    if changes.get("on_hand", inventory.on_hand) < inventory.reserved:
        raise Conflict("Stock on hand cannot be lower than the reserved quantity.")
    if "bin_location" in changes:
        # An empty string clears the bin location.
        changes["bin_location"] = changes["bin_location"].strip() or None
    for field, value in changes.items():
        setattr(inventory, field, value)
    db.commit()
    return inventory
