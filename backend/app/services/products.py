import secrets
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.errors import AppError, Conflict, NotFound
from app.images import IMAGE_TYPES, detect_image_type
from app.models import Inventory, Product, ProductImage, Staff, Tag, TagKind
from app.permissions import Permission, require
from app.schemas import (
    ProductCreate,
    ProductImageUpdate,
    ProductTagsUpdate,
    ProductUpdate,
    TagCreate,
)
from app.storage import Storage
from app.text import slugify


class InvalidImage(AppError):
    status_code = 422
    code = "invalid_image"


def _with_details(query: Select) -> Select:
    return query.options(selectinload(Product.tags), selectinload(Product.images))


def _tag_filter(kind: TagKind, slug: str):
    return Product.tags.any((Tag.kind == kind) & (Tag.slug == slug))


SORTS = {
    "name": (Product.name,),
    "newest": (Product.created_at.desc(), Product.id.desc()),
    "price_asc": (Product.price, Product.name),
    "price_desc": (Product.price.desc(), Product.name),
}


def list_active_products(
    db: Session,
    *,
    occasion: str | None = None,
    recipient: str | None = None,
    q: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    sort: str = "name",
) -> list[Product]:
    query = select(Product).where(Product.is_active)
    if occasion:
        query = query.where(_tag_filter(TagKind.OCCASION, occasion))
    if recipient:
        query = query.where(_tag_filter(TagKind.RECIPIENT, recipient))
    for word in (q or "").split()[:8]:
        # Every word must appear in the name, description or a tag name.
        pattern = f"%{_escape_like(word)}%"
        query = query.where(
            Product.name.ilike(pattern, escape="\\")
            | Product.description.ilike(pattern, escape="\\")
            | Product.tags.any(Tag.name.ilike(pattern, escape="\\"))
        )
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    query = _with_details(query).options(selectinload(Product.inventory))
    return list(db.scalars(query.order_by(*SORTS[sort])))


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_active_product_by_slug(db: Session, slug: str) -> Product:
    product = db.scalar(
        _with_details(select(Product).where(Product.slug == slug, Product.is_active)).options(
            selectinload(Product.inventory)
        )
    )
    if product is None:
        raise NotFound("Product not found.")
    return product


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("Product not found.")
    return product


def ensure_unique(db: Session, *, sku: str | None, slug: str | None, exclude_id: int | None):
    if sku is not None:
        existing = db.scalar(select(Product.id).where(Product.sku == sku))
        if existing is not None and existing != exclude_id:
            raise Conflict("A product with this SKU already exists.")
    if slug is not None:
        existing = db.scalar(select(Product.id).where(Product.slug == slug))
        if existing is not None and existing != exclude_id:
            raise Conflict("A product with this slug already exists.")


def create_product(db: Session, actor: Staff, data: ProductCreate) -> Product:
    require(actor, Permission.MANAGE_PRODUCTS, "Your role cannot create products.")
    ensure_unique(db, sku=data.sku, slug=data.slug, exclude_id=None)
    product = Product(**data.model_dump(), inventory=Inventory(), tags=[], images=[])
    db.add(product)
    db.commit()
    return product


def update_product(db: Session, actor: Staff, product_id: int, data: ProductUpdate) -> Product:
    changes = data.model_dump(exclude_none=True)
    message = (
        "Your role cannot change prices."
        if "price" in changes
        else "Your role cannot change products."
    )
    require(actor, Permission.MANAGE_PRODUCTS, message)
    product = get_product(db, product_id)
    ensure_unique(db, sku=None, slug=changes.get("slug"), exclude_id=product.id)
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    return product


# Tags


def list_tags(db: Session) -> list[Tag]:
    return list(db.scalars(select(Tag).order_by(Tag.kind, Tag.name)))


def create_tag(db: Session, actor: Staff, data: TagCreate) -> Tag:
    require(actor, Permission.MANAGE_PRODUCTS, "Your role cannot add tags.")
    slug = data.slug or slugify(data.name)
    if db.scalar(select(Tag.id).where(Tag.kind == data.kind, Tag.slug == slug)) is not None:
        raise Conflict("This tag already exists.")
    tag = Tag(kind=data.kind, slug=slug, name=data.name.strip())
    db.add(tag)
    db.commit()
    return tag


def find_tags(db: Session, kind: TagKind, slugs: list[str]) -> list[Tag]:
    wanted = set(slugs)
    tags = list(db.scalars(select(Tag).where(Tag.kind == kind, Tag.slug.in_(wanted))))
    missing = wanted - {tag.slug for tag in tags}
    if missing:
        raise NotFound(f"Unknown {kind.value} tags: {', '.join(sorted(missing))}.")
    return tags


def set_product_tags(
    db: Session, actor: Staff, product_id: int, data: ProductTagsUpdate
) -> Product:
    require(actor, Permission.MANAGE_PRODUCTS, "Your role cannot change products.")
    product = get_product(db, product_id)
    tags = find_tags(db, TagKind.OCCASION, data.occasions) + find_tags(
        db, TagKind.RECIPIENT, data.recipients
    )
    product.tags = sorted(tags, key=lambda tag: tag.name)
    db.commit()
    return product


# Images


def check_image(data: bytes) -> str:
    """Return the image's content type, or raise if it isn't an accepted image."""
    if len(data) > get_settings().max_image_bytes:
        raise InvalidImage("Images must be 5 MB or smaller.")
    content_type = detect_image_type(data)
    if content_type is None:
        raise InvalidImage("Images must be JPEG, PNG or WebP files.")
    return content_type


def store_image(
    storage: Storage, product: Product, *, filename: str, data: bytes, alt_text: str = ""
) -> ProductImage:
    """Upload the file and attach it as the product's last image. Does not commit."""
    content_type = check_image(data)
    key = f"products/{product.id}/{secrets.token_hex(8)}.{IMAGE_TYPES[content_type]}"
    storage.put(key, data, content_type)
    image = ProductImage(
        storage_key=key,
        original_filename=filename[:255],
        content_type=content_type,
        alt_text=alt_text or product.name,
        position=len(product.images),
    )
    product.images.append(image)
    return image


def add_image(
    db: Session,
    storage: Storage,
    actor: Staff,
    product_id: int,
    *,
    filename: str,
    data: bytes,
    alt_text: str = "",
) -> ProductImage:
    require(actor, Permission.MANAGE_PRODUCTS, "Your role cannot change products.")
    product = get_product(db, product_id)
    image = store_image(storage, product, filename=filename, data=data, alt_text=alt_text)
    try:
        db.commit()
    except Exception:
        storage.delete(image.storage_key)
        raise
    return image


def _get_image(product: Product, image_id: int) -> ProductImage:
    for image in product.images:
        if image.id == image_id:
            return image
    raise NotFound("Image not found.")


def _renumber(images: list[ProductImage]) -> None:
    for position, image in enumerate(images):
        image.position = position


def update_image(
    db: Session, actor: Staff, product_id: int, image_id: int, data: ProductImageUpdate
) -> ProductImage:
    require(actor, Permission.MANAGE_PRODUCTS, "Your role cannot change products.")
    product = get_product(db, product_id)
    image = _get_image(product, image_id)
    if data.alt_text is not None:
        image.alt_text = data.alt_text
    if data.position is not None:
        ordered = [i for i in product.images if i.id != image.id]
        ordered.insert(min(data.position, len(ordered)), image)
        _renumber(ordered)
        product.images.sort(key=lambda i: i.position)
    db.commit()
    return image


def delete_image(db: Session, storage: Storage, actor: Staff, product_id: int, image_id: int):
    require(actor, Permission.MANAGE_PRODUCTS, "Your role cannot change products.")
    product = get_product(db, product_id)
    image = _get_image(product, image_id)
    product.images.remove(image)
    _renumber(product.images)
    db.commit()
    storage.delete(image.storage_key)
