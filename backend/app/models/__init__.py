"""All models, imported here so Alembic and the app see every table."""

from app.models.accounts import Address, Customer, Staff, StaffRole
from app.models.agents import (
    ActorKind,
    AgentMessage,
    AgentRun,
    AgentToolCall,
    ApprovalRequest,
    ApprovalStatus,
    AuditEntry,
    Risk,
    RunStatus,
)
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
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument, ProductVector
from app.models.orders import (
    Cart,
    CartItem,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentEvent,
    Refund,
    Shipment,
)
from app.models.suppliers import PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, Supplier

__all__ = [
    "ActorKind",
    "AgentMessage",
    "AgentRun",
    "AgentToolCall",
    "ApprovalRequest",
    "ApprovalStatus",
    "AuditEntry",
    "Risk",
    "RunStatus",
    "Address",
    "Base",
    "Cart",
    "CartItem",
    "Customer",
    "Inventory",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "Order",
    "OrderEvent",
    "OrderItem",
    "OrderStatus",
    "PaymentEvent",
    "Product",
    "ProductImage",
    "ProductVector",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseOrderStatus",
    "Refund",
    "Shipment",
    "Staff",
    "StaffRole",
    "StockAdjustment",
    "StockReason",
    "Supplier",
    "Tag",
    "TagKind",
    "product_tags",
]
