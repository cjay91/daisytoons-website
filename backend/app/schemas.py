"""Request and response bodies for the API."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from app.config import get_settings
from app.models import StaffRole

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


class ProductOut(ORMModel):
    id: int
    sku: str
    slug: str
    name: str
    description: str
    price: Decimal
    is_active: bool

    @computed_field
    @property
    def currency(self) -> str:
        return get_settings().currency


class InventoryUpdate(BaseModel):
    on_hand: int | None = Field(default=None, ge=0)
    reorder_point: int | None = Field(default=None, ge=0)
    bin_location: str | None = Field(default=None, max_length=50)


class InventoryOut(ORMModel):
    product_id: int
    on_hand: int
    reserved: int
    reorder_point: int
    bin_location: str | None
