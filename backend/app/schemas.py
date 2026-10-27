"""Request and response bodies for the API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, model_validator

from app.config import get_settings
from app.models import OrderStatus, PurchaseOrderStatus, StaffRole, StockReason, TagKind
from app.pricing import DISTRICTS
from app.storage import public_url

PasswordStr = Annotated[str, Field(min_length=8, max_length=128)]
SlugStr = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
PriceDecimal = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CustomerRegister(BaseModel):
    email: EmailStr
    password: PasswordStr
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)


class CustomerOut(ORMModel):
    id: int
    email: str
    full_name: str
    phone: str | None
    created_at: datetime


class StaffCreate(BaseModel):
    email: EmailStr
    password: PasswordStr
    full_name: str = Field(min_length=1, max_length=200)
    role: StaffRole


class StaffOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: StaffRole
    is_active: bool


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    slug: SlugStr
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    price: PriceDecimal
    is_active: bool = True


class ProductUpdate(BaseModel):
    slug: SlugStr | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: PriceDecimal | None = None
    is_active: bool | None = None


class TagOut(ORMModel):
    id: int
    kind: TagKind
    slug: str
    name: str


class TagCreate(BaseModel):
    kind: TagKind
    name: str = Field(min_length=1, max_length=100)
    slug: SlugStr | None = None


class ProductTagsUpdate(BaseModel):
    """The product's full set of tags, by slug. Replaces whatever it had."""

    occasions: list[str] = []
    recipients: list[str] = []


class ProductImageOut(ORMModel):
    id: int
    alt_text: str
    position: int
    storage_key: str = Field(exclude=True)

    @computed_field
    @property
    def url(self) -> str:
        return public_url(self.storage_key)


class ProductImageUpdate(BaseModel):
    alt_text: str | None = Field(default=None, max_length=300)
    position: int | None = Field(default=None, ge=0)


class ProductOut(ORMModel):
    id: int
    sku: str
    slug: str
    name: str
    description: str
    price: Decimal
    is_active: bool
    tags: list[TagOut]
    images: list[ProductImageOut]

    @computed_field
    @property
    def currency(self) -> str:
        return get_settings().currency


class StoreProductOut(ProductOut):
    """A product as the storefront shows it, with how many can be bought right now."""

    inventory: "InventoryOut | None" = Field(default=None, exclude=True)

    @computed_field
    @property
    def available(self) -> int:
        if self.inventory is None:
            return 0
        return max(self.inventory.on_hand - self.inventory.reserved, 0)


class InventoryUpdate(BaseModel):
    """Stock on hand is not here: it changes only through stock adjustments, which are logged."""

    reorder_point: int | None = Field(default=None, ge=0)
    bin_location: str | None = Field(default=None, max_length=50)


class InventoryOut(ORMModel):
    product_id: int
    on_hand: int
    reserved: int
    reorder_point: int
    bin_location: str | None


class StockAdjustmentCreate(BaseModel):
    """Either a change (12 received) or a count (37 on the shelf). Exactly one is required."""

    reason: StockReason
    quantity_change: int | None = None
    new_on_hand: int | None = Field(default=None, ge=0)
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _exactly_one_amount(self) -> "StockAdjustmentCreate":
        if (self.quantity_change is None) == (self.new_on_hand is None):
            raise ValueError("Give either quantity_change or new_on_hand, not both.")
        if self.reason == StockReason.IMPORT:
            raise ValueError("The import reason is only for the import script.")
        if self.reason in (StockReason.SALE, StockReason.ORDER_CANCELLED):
            raise ValueError("That reason is only for orders.")
        return self


class StockAdjustmentOut(ORMModel):
    id: int
    product_id: int
    staff_id: int | None
    reason: StockReason
    quantity_change: int
    on_hand_before: int
    on_hand_after: int
    note: str
    created_at: datetime


class CartItemOut(BaseModel):
    product_id: int
    slug: str
    name: str
    image_url: str | None
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    # How many more the shop could sell right now; 0 when the product is no longer sold.
    available: int


class CartOut(BaseModel):
    # Guests keep this and send it back as the X-Cart-Token header. Empty when there's no cart.
    token: str | None
    items: list[CartItemOut]
    item_count: int
    subtotal: Decimal
    gift_wrap: bool
    gift_message: str
    gift_wrap_fee: Decimal
    # What gift wrap costs when it's switched on.
    gift_wrap_price: Decimal
    # Delivery depends on the district, so the cart shows both prices.
    delivery_fee_colombo: Decimal
    delivery_fee_other: Decimal
    free_delivery_over: Decimal
    currency: str


class CartItemSet(BaseModel):
    quantity: int = Field(ge=0, le=20)


class CartUpdate(BaseModel):
    gift_wrap: bool | None = None
    gift_message: str | None = Field(default=None, max_length=300)


class DeliveryAddress(BaseModel):
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    district: str
    postal_code: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _known_district(self) -> "DeliveryAddress":
        if self.district not in DISTRICTS:
            raise ValueError(f"District must be one of: {', '.join(DISTRICTS)}.")
        return self


class CheckoutRequest(BaseModel):
    # Required for guests. Logged-in customers can leave it out to use their account email.
    email: EmailStr | None = None
    customer_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=7, max_length=32)
    address: DeliveryAddress
    notes: str | None = Field(default=None, max_length=1000)


class PaymentForm(BaseModel):
    """The storefront posts these fields, as an HTML form, to action_url."""

    action_url: str
    fields: dict[str, str]


class CheckoutOut(BaseModel):
    order_number: str
    order_key: str
    total: Decimal
    currency: str
    expires_at: datetime
    payment: PaymentForm


class OrderItemOut(ORMModel):
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class OrderEventOut(ORMModel):
    to_status: OrderStatus
    note: str
    created_at: datetime


class ShipmentOut(ORMModel):
    courier: str
    tracking_number: str
    tracking_url: str | None
    shipped_at: datetime
    delivered_at: datetime | None


class OrderSummaryOut(ORMModel):
    order_number: str
    status: OrderStatus
    total: Decimal
    item_count: int
    created_at: datetime


class OrderOut(ORMModel):
    order_number: str
    status: OrderStatus
    email: str
    customer_name: str
    phone: str
    items: list[OrderItemOut]
    subtotal: Decimal
    gift_wrap: bool
    gift_wrap_fee: Decimal
    gift_message: str
    delivery_fee: Decimal
    total: Decimal
    shipping_address: dict[str, Any]
    expires_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    # Status history, oldest first: what the customer sees as order tracking.
    events: list[OrderEventOut]
    shipment: ShipmentOut | None
    # The private key for the order page; only shown to the customer who owns the order.
    access_key: str | None = None

    @computed_field
    @property
    def currency(self) -> str:
        return get_settings().currency


class AddressIn(BaseModel):
    label: str | None = Field(default=None, max_length=50)
    recipient_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    district: str
    postal_code: str | None = Field(default=None, max_length=20)
    is_default: bool = False

    @model_validator(mode="after")
    def _known_district(self) -> "AddressIn":
        if self.district not in DISTRICTS:
            raise ValueError(f"District must be one of: {', '.join(DISTRICTS)}.")
        return self


class AddressOut(ORMModel):
    id: int
    label: str | None
    recipient_name: str
    phone: str | None
    line1: str
    line2: str | None
    city: str
    # Stored in the address's region column.
    district: str | None = Field(validation_alias="region")
    postal_code: str | None
    is_default: bool


# Staff: orders and fulfilment


class StaffBrief(ORMModel):
    id: int
    full_name: str


class StaffOrderEventOut(ORMModel):
    from_status: OrderStatus | None
    to_status: OrderStatus
    note: str
    staff: StaffBrief | None
    created_at: datetime


class StaffShipmentOut(ShipmentOut):
    staff: StaffBrief | None
    notified_at: datetime | None


class RefundOut(ORMModel):
    id: int
    amount: Decimal
    reason: str
    reference: str | None
    restocked: bool
    staff: StaffBrief | None
    created_at: datetime


class PaymentEventOut(ORMModel):
    provider: str
    provider_payment_id: str | None
    status_code: str
    signature_valid: bool
    outcome: str
    received_at: datetime


class StaffOrderSummaryOut(ORMModel):
    order_number: str
    status: OrderStatus
    customer_name: str
    email: str
    district: str
    total: Decimal
    item_count: int
    gift_wrap: bool
    needs_attention: str | None
    created_at: datetime
    paid_at: datetime | None


class StaffOrderListOut(BaseModel):
    orders: list[StaffOrderSummaryOut]
    total: int


class StaffOrderOut(OrderOut):
    notes: str | None
    needs_attention: str | None
    payment_reference: str | None
    confirmation_sent_at: datetime | None
    customer_id: int | None
    events: list[StaffOrderEventOut]  # type: ignore[assignment]
    shipment: StaffShipmentOut | None  # type: ignore[assignment]
    refunds: list[RefundOut]
    payment_events: list[PaymentEventOut] = []
    refunded_total: Decimal
    refundable: Decimal
    # The next steps staff can take, so the console only shows buttons that will work.
    actions: list[str]


class OrderNumbers(BaseModel):
    order_numbers: list[str] = Field(min_length=1, max_length=100)


class ShipmentCreate(BaseModel):
    courier: str = Field(min_length=1, max_length=50)
    tracking_number: str = Field(min_length=1, max_length=100)
    tracking_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")


class OrderCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    # The gateway's refund reference, for an order that was paid.
    refund_reference: str | None = Field(default=None, max_length=100)


class RefundCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    reason: str = Field(min_length=1, max_length=1000)
    reference: str | None = Field(default=None, max_length=100)
    # Put the items back on the shelf. Only with a full refund.
    restock: bool = False


class AttentionResolve(BaseModel):
    note: str = Field(default="", max_length=1000)


class PickOrderLine(BaseModel):
    order_number: str
    quantity: int


class PickListItem(BaseModel):
    product_id: int
    sku: str
    name: str
    bin_location: str | None
    quantity: int
    orders: list[PickOrderLine]


class PickListOut(BaseModel):
    order_numbers: list[str]
    items: list[PickListItem]


# Staff: catalog and stock


class StaffProductOut(ProductOut):
    inventory: InventoryOut | None

    @computed_field
    @property
    def available(self) -> int:
        if self.inventory is None:
            return 0
        return max(self.inventory.on_hand - self.inventory.reserved, 0)


class LowStockOut(BaseModel):
    product_id: int
    sku: str
    name: str
    is_active: bool
    on_hand: int
    reserved: int
    available: int
    reorder_point: int
    bin_location: str | None
    # Ordered from suppliers and not yet received.
    on_order: int


# Staff: suppliers and purchase orders


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    notes: str | None = None
    is_active: bool = True


class SupplierOut(ORMModel):
    id: int
    name: str
    email: str | None
    phone: str | None
    notes: str | None
    is_active: bool


class PurchaseOrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=100000)
    unit_cost: PriceDecimal


class PurchaseOrderIn(BaseModel):
    supplier_id: int
    expected_at: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PurchaseOrderItemIn] = Field(min_length=1, max_length=200)


class PurchaseOrderProduct(ORMModel):
    sku: str
    name: str


class PurchaseOrderItemOut(ORMModel):
    product_id: int
    quantity: int
    unit_cost: Decimal
    product: PurchaseOrderProduct

    @computed_field
    @property
    def line_total(self) -> Decimal:
        return self.unit_cost * self.quantity


class PurchaseOrderOut(ORMModel):
    id: int
    supplier: SupplierOut
    status: PurchaseOrderStatus
    expected_at: date | None
    notes: str | None
    items: list[PurchaseOrderItemOut]
    created_at: datetime
    sent_at: datetime | None
    received_at: datetime | None

    @computed_field
    @property
    def total(self) -> Decimal:
        return sum((item.line_total for item in self.items), Decimal("0"))


# Staff: reports


class TopProduct(BaseModel):
    product_id: int
    name: str
    quantity: int
    revenue: Decimal


class DaySales(BaseModel):
    day: date
    orders: int
    revenue: Decimal


class DailyReportOut(BaseModel):
    day: date
    orders: int
    revenue: Decimal
    items_sold: int
    average_order: Decimal
    refunds: Decimal
    top_products: list[TopProduct]
    # Right now, not on the chosen day.
    waiting_to_ship: int
    needs_attention: int
    low_stock: int
    last_14_days: list[DaySales]
    currency: str
