from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status

from app.api.deps import DB, ClientIP, CurrentStaff, FileStorage, RateCounter
from app.config import get_settings
from app.errors import InvalidCredentials
from app.models import Staff
from app.ratelimit import LOGIN_PER_ACCOUNT, LOGIN_PER_IP, TWO_FACTOR_PER_ACCOUNT, check
from app.schemas import (
    InventoryOut,
    InventoryUpdate,
    LoginRequest,
    ProductCreate,
    ProductImageOut,
    ProductImageUpdate,
    ProductOut,
    ProductTagsUpdate,
    ProductUpdate,
    StaffCreate,
    StaffLoginOut,
    StaffOut,
    StaffProductOut,
    StockAdjustmentCreate,
    StockAdjustmentOut,
    TagCreate,
    TagOut,
    Token,
    TwoFactorCode,
    TwoFactorLogin,
    TwoFactorSetupOut,
)
from app.security import create_access_token, decode_access_token
from app.services import accounts, inventory, products, two_factor

router = APIRouter(prefix="/staff", tags=["staff"])


@router.post("/auth/login")
def login(db: DB, counter: RateCounter, ip: ClientIP, body: LoginRequest) -> StaffLoginOut:
    check(counter, LOGIN_PER_IP, "staff", ip)
    check(counter, LOGIN_PER_ACCOUNT, "staff", ip, body.email)
    staff = accounts.authenticate_staff(db, email=body.email, password=body.password)
    if two_factor.is_enabled(staff):
        # The password was right; a code from the authenticator app finishes the login.
        challenge = create_access_token("staff_2fa", staff.id, minutes=5)
        return StaffLoginOut(two_factor_required=True, challenge_token=challenge)
    return StaffLoginOut(access_token=create_access_token("staff", staff.id))


@router.post("/auth/two-factor")
def login_two_factor(db: DB, counter: RateCounter, body: TwoFactorLogin) -> Token:
    staff_id = decode_access_token(body.challenge_token, "staff_2fa")
    staff = db.get(Staff, staff_id) if staff_id else None
    if staff is None or not staff.is_active:
        raise InvalidCredentials("Your login timed out. Enter your password again.")
    check(counter, TWO_FACTOR_PER_ACCOUNT, str(staff.id))
    two_factor.verify_login(db, staff, body.code)
    return Token(access_token=create_access_token("staff", staff.id))


@router.post("/me/two-factor/setup")
def start_two_factor(db: DB, staff: CurrentStaff) -> TwoFactorSetupOut:
    secret, url = two_factor.start_setup(db, staff)
    return TwoFactorSetupOut(secret=secret, otpauth_url=url)


@router.post("/me/two-factor/enable")
def enable_two_factor(
    db: DB, counter: RateCounter, staff: CurrentStaff, body: TwoFactorCode
) -> StaffOut:
    check(counter, TWO_FACTOR_PER_ACCOUNT, str(staff.id))
    return StaffOut.model_validate(two_factor.enable(db, staff, body.code))


@router.post("/members/{staff_id}/reset-two-factor")
def reset_two_factor(db: DB, staff: CurrentStaff, staff_id: int) -> StaffOut:
    return StaffOut.model_validate(two_factor.reset(db, staff, staff_id))


@router.get("/me")
def me(staff: CurrentStaff) -> StaffOut:
    return StaffOut.model_validate(staff)


@router.get("/members")
def list_members(db: DB, staff: CurrentStaff) -> list[StaffOut]:
    return [StaffOut.model_validate(s) for s in accounts.list_staff(db, staff)]


@router.post("/members", status_code=status.HTTP_201_CREATED)
def create_member(db: DB, staff: CurrentStaff, body: StaffCreate) -> StaffOut:
    return StaffOut.model_validate(accounts.create_staff(db, staff, **body.model_dump()))


# Products


@router.get("/products")
def list_products(
    db: DB, staff: CurrentStaff, q: Annotated[str | None, Query(max_length=100)] = None
) -> list[StaffProductOut]:
    """Every product, including ones no longer sold, with stock."""
    return [StaffProductOut.model_validate(p) for p in products.list_staff_products(db, staff, q=q)]


@router.get("/products/{product_id}")
def get_product(db: DB, staff: CurrentStaff, product_id: int) -> StaffProductOut:
    return StaffProductOut.model_validate(products.get_staff_product(db, staff, product_id))


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(db: DB, staff: CurrentStaff, body: ProductCreate) -> ProductOut:
    return ProductOut.model_validate(products.create_product(db, staff, body))


@router.patch("/products/{product_id}")
def update_product(db: DB, staff: CurrentStaff, product_id: int, body: ProductUpdate) -> ProductOut:
    return ProductOut.model_validate(products.update_product(db, staff, product_id, body))


@router.put("/products/{product_id}/tags")
def set_product_tags(
    db: DB, staff: CurrentStaff, product_id: int, body: ProductTagsUpdate
) -> ProductOut:
    return ProductOut.model_validate(products.set_product_tags(db, staff, product_id, body))


@router.post("/tags", status_code=status.HTTP_201_CREATED)
def create_tag(db: DB, staff: CurrentStaff, body: TagCreate) -> TagOut:
    return TagOut.model_validate(products.create_tag(db, staff, body))


# Images


@router.post("/products/{product_id}/images", status_code=status.HTTP_201_CREATED)
def upload_image(
    db: DB,
    storage: FileStorage,
    staff: CurrentStaff,
    product_id: int,
    file: Annotated[UploadFile, File()],
    alt_text: Annotated[str, Form(max_length=300)] = "",
) -> ProductImageOut:
    # A plain def keeps the database work off the event loop. Read one byte past the limit,
    # so an oversized file is rejected without reading all of it.
    data = file.file.read(get_settings().max_image_bytes + 1)
    image = products.add_image(
        db, storage, staff, product_id, filename=file.filename or "", data=data, alt_text=alt_text
    )
    return ProductImageOut.model_validate(image)


@router.patch("/products/{product_id}/images/{image_id}")
def update_image(
    db: DB, staff: CurrentStaff, product_id: int, image_id: int, body: ProductImageUpdate
) -> ProductImageOut:
    image = products.update_image(db, staff, product_id, image_id, body)
    return ProductImageOut.model_validate(image)


@router.delete("/products/{product_id}/images/{image_id}", status_code=204)
def delete_image(
    db: DB, storage: FileStorage, staff: CurrentStaff, product_id: int, image_id: int
) -> Response:
    products.delete_image(db, storage, staff, product_id, image_id)
    return Response(status_code=204)


# Stock


@router.get("/products/{product_id}/inventory")
def get_inventory(db: DB, staff: CurrentStaff, product_id: int) -> InventoryOut:
    return InventoryOut.model_validate(inventory.get_inventory(db, staff, product_id))


@router.patch("/products/{product_id}/inventory")
def update_inventory(
    db: DB, staff: CurrentStaff, product_id: int, body: InventoryUpdate
) -> InventoryOut:
    return InventoryOut.model_validate(inventory.update_inventory(db, staff, product_id, body))


@router.post("/products/{product_id}/stock-adjustments", status_code=status.HTTP_201_CREATED)
def adjust_stock(
    db: DB, staff: CurrentStaff, product_id: int, body: StockAdjustmentCreate
) -> StockAdjustmentOut:
    adjustment = inventory.adjust_stock(db, staff, product_id, body)
    return StockAdjustmentOut.model_validate(adjustment)


@router.get("/products/{product_id}/stock-adjustments")
def list_stock_adjustments(
    db: DB, staff: CurrentStaff, product_id: int
) -> list[StockAdjustmentOut]:
    return [
        StockAdjustmentOut.model_validate(a)
        for a in inventory.list_adjustments(db, staff, product_id)
    ]
