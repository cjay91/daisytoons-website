"""Request and response bodies for the API."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, model_validator

from app.config import get_settings
from app.models import StaffRole, StockReason, TagKind
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
