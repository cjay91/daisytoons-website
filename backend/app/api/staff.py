from fastapi import APIRouter, status

from app.api.deps import DB, CurrentStaff
from app.schemas import (
    InventoryOut,
    InventoryUpdate,
    LoginRequest,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    StaffCreate,
    StaffOut,
    Token,
)
from app.security import create_access_token
from app.services import accounts, products

router = APIRouter(prefix="/staff", tags=["staff"])


@router.post("/auth/login")
def login(db: DB, body: LoginRequest) -> Token:
    staff = accounts.authenticate_staff(db, email=body.email, password=body.password)
    return Token(access_token=create_access_token("staff", staff.id))


@router.get("/me")
def me(staff: CurrentStaff) -> StaffOut:
    return StaffOut.model_validate(staff)


@router.get("/members")
def list_members(db: DB, staff: CurrentStaff) -> list[StaffOut]:
    return [StaffOut.model_validate(s) for s in accounts.list_staff(db, staff)]


@router.post("/members", status_code=status.HTTP_201_CREATED)
def create_member(db: DB, staff: CurrentStaff, body: StaffCreate) -> StaffOut:
    return StaffOut.model_validate(accounts.create_staff(db, staff, **body.model_dump()))


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(db: DB, staff: CurrentStaff, body: ProductCreate) -> ProductOut:
    return ProductOut.model_validate(products.create_product(db, staff, body))


@router.patch("/products/{product_id}")
def update_product(db: DB, staff: CurrentStaff, product_id: int, body: ProductUpdate) -> ProductOut:
    return ProductOut.model_validate(products.update_product(db, staff, product_id, body))


@router.get("/products/{product_id}/inventory")
def get_inventory(db: DB, staff: CurrentStaff, product_id: int) -> InventoryOut:
    return InventoryOut.model_validate(products.get_inventory(db, staff, product_id))


@router.patch("/products/{product_id}/inventory")
def update_inventory(
    db: DB, staff: CurrentStaff, product_id: int, body: InventoryUpdate
) -> InventoryOut:
    return InventoryOut.model_validate(products.update_inventory(db, staff, product_id, body))
