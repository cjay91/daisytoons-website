"""Request and response bodies for the API."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, model_validator

from app.config import get_settings
from app.models import OrderStatus, StaffRole, StockReason, TagKind
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
        if self.reason == StockReason.SALE:
            raise ValueError("The sale reason is only for paid orders.")
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
