"""Import products from a CSV file. See docs/specs/part-3-catalog-inventory.md.

Every row is checked before anything is saved; one bad row means nothing is imported.
Products are matched by SKU, so the same file can be imported again safely.
"""

import csv
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError
from app.models import Inventory, Product, Tag, TagKind
from app.services.inventory import record_import_stock
from app.services.products import check_image, store_image
from app.storage import Storage
from app.text import slugify

REQUIRED_COLUMNS = {"sku", "name", "price", "on_hand"}
KNOWN_COLUMNS = REQUIRED_COLUMNS | {
    "slug",
    "description",
    "occasions",
    "recipients",
    "reorder_point",
    "bin_location",
    "images",
    "active",
}
YES = {"yes", "y", "true", "1"}
NO = {"no", "n", "false", "0"}


class ImportFailed(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"{len(errors)} problem(s) found")
        self.errors = errors


@dataclass
class ProductRow:
    line: int
    sku: str
    name: str
    slug: str
    description: str
    price: Decimal
    on_hand: int
    reorder_point: int
    bin_location: str | None
    active: bool
    occasions: list[Tag]
    recipients: list[Tag]
    images: list[Path]


@dataclass
class ImportSummary:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    stock_changes: int = 0
    images_uploaded: int = 0


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _read_csv(path: Path) -> list[dict[str, str]]:
    # utf-8-sig drops the marker Excel puts at the start of CSV files.
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = {(c or "").strip().lower() for c in reader.fieldnames or []}
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ImportFailed([f"Missing column(s): {', '.join(sorted(missing))}."])
        unknown = columns - KNOWN_COLUMNS - {""}
        if unknown:
            raise ImportFailed([f"Unknown column(s): {', '.join(sorted(unknown))}."])
        return [
            {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader
        ]


def _tag_lookup(db: Session) -> dict[TagKind, dict[str, Tag]]:
    lookup: dict[TagKind, dict[str, Tag]] = {kind: {} for kind in TagKind}
    for tag in db.scalars(select(Tag)):
        lookup[tag.kind][tag.slug] = tag
        lookup[tag.kind][tag.name.lower()] = tag
    return lookup


def _whole_number(
    raw: dict[str, str], column: str, default: int | None, problems: list[str]
) -> int:
    value = raw.get(column, "")
    if not value and default is not None:
        return default
    if not value.isdigit():
        problems.append(f"{column} {value!r} must be a whole number, 0 or more")
        return 0
    return int(value)


def _find_tags(
    value: str, kind: TagKind, tags: dict[TagKind, dict[str, Tag]], problems: list[str]
) -> list[Tag]:
    found: list[Tag] = []
    for item in _split(value):
        tag = tags[kind].get(item.lower()) or tags[kind].get(slugify(item))
        if tag is None:
            problems.append(f"unknown {kind.value} tag {item!r}")
        elif tag not in found:
            found.append(tag)
    return found


def _parse_rows(
    db: Session, raw_rows: list[dict[str, str]], images_dir: Path | None
) -> list[ProductRow]:
    errors: list[str] = []
    rows: list[ProductRow] = []
    tags = _tag_lookup(db)
    seen_skus: dict[str, int] = {}
    seen_slugs: dict[str, int] = {}

    for line, raw in enumerate(raw_rows, start=2):  # line 1 is the header
        if not any(raw.values()):
            continue
        problems: list[str] = []

        sku = raw.get("sku", "")
        name = raw.get("name", "")
        if not sku:
            problems.append("sku is required")
        elif len(sku) > 64:
            problems.append("sku is longer than 64 characters")
        elif sku in seen_skus:
            problems.append(f"sku {sku} is also on line {seen_skus[sku]}")
        if not name:
            problems.append("name is required")

        slug = raw.get("slug") or slugify(name)
        if name and not slug:
            problems.append("can't make a web address from the name; add a slug")
        elif slug and slug != slugify(slug):
            problems.append("slug may only contain lowercase letters, numbers and dashes")
        elif slug in seen_slugs:
            problems.append(f"slug {slug} is also on line {seen_slugs[slug]}")

        price = Decimal(0)
        try:
            price = Decimal(raw.get("price", "").replace(",", ""))
            if price < 0 or price != price.quantize(Decimal("0.01")) or price >= 10**8:
                raise InvalidOperation
            price = price.quantize(Decimal("0.01"))
        except InvalidOperation:
            problems.append(f"price {raw.get('price')!r} must be an amount like 1250.00")

        on_hand = _whole_number(raw, "on_hand", None, problems)
        reorder_point = _whole_number(raw, "reorder_point", 0, problems)

        active_text = raw.get("active", "").lower()
        if active_text and active_text not in YES | NO:
            problems.append(f"active {raw.get('active')!r} must be yes or no")
        active = active_text not in NO

        occasions = _find_tags(raw.get("occasions", ""), TagKind.OCCASION, tags, problems)
        recipients = _find_tags(raw.get("recipients", ""), TagKind.RECIPIENT, tags, problems)

        images: list[Path] = []
        for filename in _split(raw.get("images", "")):
            if images_dir is None:
                problems.append("images are listed but no --images folder was given")
                break
            image_path = images_dir / filename
            if not image_path.is_file():
                problems.append(f"image {filename} not found in {images_dir}")
                continue
            try:
                check_image(image_path.read_bytes())
            except AppError as exc:
                problems.append(f"image {filename}: {exc.message}")
                continue
            images.append(image_path)

        if problems:
            errors.extend(f"Line {line}: {problem}." for problem in problems)
            continue
        seen_skus[sku] = line
        seen_slugs[slug] = line
        rows.append(
            ProductRow(
                line=line,
                sku=sku,
                name=name,
                slug=slug,
                description=raw.get("description", ""),
                price=price,
                on_hand=on_hand,
                reorder_point=reorder_point,
                bin_location=raw.get("bin_location") or None,
                active=active,
                occasions=occasions,
                recipients=recipients,
                images=images,
            )
        )

    errors.extend(_check_against_database(db, rows))
    if errors:
        raise ImportFailed(errors)
    if not rows:
        raise ImportFailed(["The file has no products in it."])
    return rows


def _check_against_database(db: Session, rows: list[ProductRow]) -> list[str]:
    errors = []
    by_slug = {
        p.slug: p
        for p in db.scalars(select(Product).where(Product.slug.in_([r.slug for r in rows])))
    }
    existing = _existing_products(db, rows)
    for row in rows:
        owner = by_slug.get(row.slug)
        if owner is not None and owner.sku != row.sku:
            errors.append(f"Line {row.line}: slug {row.slug} already belongs to {owner.sku}.")
        product = existing.get(row.sku)
        if product is not None and row.on_hand < product.inventory.reserved:
            errors.append(
                f"Line {row.line}: on_hand {row.on_hand} is below the "
                f"{product.inventory.reserved} reserved for orders."
            )
    return errors


def _existing_products(db: Session, rows: list[ProductRow]) -> dict[str, Product]:
    query = (
        select(Product)
        .where(Product.sku.in_([r.sku for r in rows]))
        .options(
            selectinload(Product.tags),
            selectinload(Product.images),
            selectinload(Product.inventory),
        )
    )
    return {p.sku: p for p in db.scalars(query)}


def import_products(
    db: Session,
    storage: Storage,
    csv_path: Path,
    images_dir: Path | None = None,
    *,
    dry_run: bool = False,
) -> ImportSummary:
    rows = _parse_rows(db, _read_csv(csv_path), images_dir)
    existing = _existing_products(db, rows)
    summary = ImportSummary()
    uploaded: list[str] = []

    try:
        for row in rows:
            product = existing.get(row.sku)
            is_new = product is None
            if is_new:
                product = Product(sku=row.sku, inventory=Inventory(), tags=[], images=[])
                db.add(product)

            fields = {
                "name": row.name,
                "slug": row.slug,
                "description": row.description,
                "price": row.price,
                "is_active": row.active,
            }
            changed = is_new or any(getattr(product, k) != v for k, v in fields.items())
            for key, value in fields.items():
                setattr(product, key, value)

            new_tags = row.occasions + row.recipients
            if {t.id for t in product.tags} != {t.id for t in new_tags}:
                product.tags = new_tags
                changed = True

            inventory = product.inventory
            if (inventory.reorder_point, inventory.bin_location) != (
                row.reorder_point,
                row.bin_location,
            ):
                inventory.reorder_point = row.reorder_point
                inventory.bin_location = row.bin_location
                changed = True

            db.flush()  # gives a new product its id, needed for stock and image records
            if record_import_stock(db, inventory, row.on_hand):
                summary.stock_changes += 1
                changed = True

            attached = {image.original_filename for image in product.images}
            for image_path in row.images:
                if image_path.name in attached:
                    continue
                summary.images_uploaded += 1
                changed = True
                if not dry_run:
                    image = store_image(
                        storage, product, filename=image_path.name, data=image_path.read_bytes()
                    )
                    uploaded.append(image.storage_key)

            target = (
                summary.created if is_new else summary.updated if changed else summary.unchanged
            )
            target.append(row.sku)

        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        for key in uploaded:
            storage.delete(key)
        raise
    return summary
