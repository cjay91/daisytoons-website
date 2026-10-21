from fastapi import APIRouter

from app.api.deps import DB
from app.schemas import ProductOut
from app.services import products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products(db: DB) -> list[ProductOut]:
    return [ProductOut.model_validate(p) for p in products.list_active_products(db)]


@router.get("/{slug}")
def get_product(db: DB, slug: str) -> ProductOut:
    return ProductOut.model_validate(products.get_active_product_by_slug(db, slug))
