from fastapi import APIRouter

from app.api.deps import DB
from app.schemas import ProductOut, TagOut
from app.services import products

router = APIRouter(tags=["products"])


@router.get("/products")
def list_products(
    db: DB, occasion: str | None = None, recipient: str | None = None
) -> list[ProductOut]:
    """Active products. Filter by tag slug, for example ?occasion=birthday&recipient=for-her."""
    found = products.list_active_products(db, occasion=occasion, recipient=recipient)
    return [ProductOut.model_validate(p) for p in found]


@router.get("/products/{slug}")
def get_product(db: DB, slug: str) -> ProductOut:
    return ProductOut.model_validate(products.get_active_product_by_slug(db, slug))


@router.get("/tags")
def list_tags(db: DB) -> list[TagOut]:
    return [TagOut.model_validate(t) for t in products.list_tags(db)]
