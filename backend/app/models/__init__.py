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
from app.models.orders import (
    Cart,
    CartItem,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentEvent,
)
from app.models.suppliers import PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, Supplier

__all__ = [
    "Address",
    "Base",
    "Cart",
    "CartItem",
    "Customer",
    "Inventory",
    "Order",
    "OrderEvent",
    "OrderItem",
    "OrderStatus",
    "PaymentEvent",
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
