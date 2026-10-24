from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import DB
from app.schemas import StoreProductOut, TagOut
from app.services import products

router = APIRouter(tags=["products"])


@router.get("/products")
def list_products(
    db: DB,
    occasion: str | None = None,
    recipient: str | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    sort: Literal["name", "newest", "price_asc", "price_desc"] = "name",
) -> list[StoreProductOut]:
    """Active products. Filter by tag slug (?occasion=birthday&recipient=for-her), by words
    in the name, description or tags (?q=teddy bear), and by price in rupees."""
    found = products.list_active_products(
        db,
        occasion=occasion,
        recipient=recipient,
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
    )
    return [StoreProductOut.model_validate(p) for p in found]


@router.get("/products/{slug}")
def get_product(db: DB, slug: str) -> StoreProductOut:
    return StoreProductOut.model_validate(products.get_active_product_by_slug(db, slug))


@router.get("/tags")
def list_tags(db: DB) -> list[TagOut]:
    return [TagOut.model_validate(t) for t in products.list_tags(db)]
