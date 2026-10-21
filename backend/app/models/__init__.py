"""All models, imported here so Alembic and the app see every table."""

from app.models.accounts import Address, Customer, Staff, StaffRole
from app.models.base import Base
from app.models.catalog import (
    Inventory,
    Product,
    ProductImage,
    StockAdjustment,
    StockReason,
    Tag,
    TagKind,
    product_tags,
)
from app.models.orders import Order, OrderItem, OrderStatus
from app.models.suppliers import PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, Supplier

__all__ = [
    "Address",
    "Base",
    "Customer",
    "Inventory",
    "Order",
    "OrderItem",
    "OrderStatus",
    "Product",
    "ProductImage",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseOrderStatus",
    "Staff",
    "StaffRole",
    "StockAdjustment",
    "StockReason",
    "Supplier",
    "Tag",
    "TagKind",
    "product_tags",
]
