import csv
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.importer import KNOWN_COLUMNS, ImportFailed, import_products
from app.models import Inventory, Product, StockAdjustment, StockReason

TEMPLATES = Path(__file__).resolve().parents[2] / "docs" / "templates"
SAMPLE_CSV = TEMPLATES / "products-sample.csv"
SAMPLE_IMAGES = TEMPLATES / "sample-images"
HEADER = "sku,name,price,on_hand,occasions,recipients,images\n"


def write_csv(tmp_path: Path, body: str, header: str = HEADER) -> Path:
    path = tmp_path / "products.csv"
    path.write_text(header + body, encoding="utf-8")
    return path


def products_by_sku(db) -> dict[str, Product]:
    return {p.sku: p for p in db.scalars(select(Product))}


def test_template_has_every_column():
    with (TEMPLATES / "products-template.csv").open() as f:
        assert set(next(csv.reader(f))) == KNOWN_COLUMNS


def test_sample_file_imports(db, storage):
    summary = import_products(db, storage, SAMPLE_CSV, SAMPLE_IMAGES)

    assert len(summary.created) == 6
    assert summary.stock_changes == 5  # the pen starts at 0, so no change to log
    assert summary.images_uploaded == 2
    assert len(storage.files) == 2

    products = products_by_sku(db)
    bear = products["SAMPLE-BEAR-003"]
    assert bear.slug == "cuddly-teddy-bear"
    assert str(bear.price) == "3200.00"
    assert {t.name for t in bear.tags} == {
        "Birthday",
        "Valentine's Day",
        "New baby",
        "For kids",
        "For her",
    }
    assert bear.inventory.on_hand == 15 and bear.inventory.bin_location == "C-2"
    assert [i.original_filename for i in bear.images] == ["teddy-bear.png"]
    assert products["SAMPLE-PEN-006"].is_active is False


def test_importing_again_changes_nothing(db, storage):
    import_products(db, storage, SAMPLE_CSV, SAMPLE_IMAGES)
    log_size = db.scalar(select(func.count()).select_from(StockAdjustment))

    summary = import_products(db, storage, SAMPLE_CSV, SAMPLE_IMAGES)

    assert (len(summary.created), len(summary.updated), len(summary.unchanged)) == (0, 0, 6)
    assert summary.stock_changes == summary.images_uploaded == 0
    assert db.scalar(select(func.count()).select_from(StockAdjustment)) == log_size
    assert len(storage.files) == 2


def test_reimport_updates_by_sku_and_logs_the_stock_change(db, storage, tmp_path):
    import_products(db, storage, write_csv(tmp_path, "MUG-1,Mug,1000,10,,,\n"))

    summary = import_products(db, storage, write_csv(tmp_path, "MUG-1,Mug,1200,7,,,\n"))

    assert summary.updated == ["MUG-1"]
    mug = products_by_sku(db)["MUG-1"]
    assert str(mug.price) == "1200.00" and mug.inventory.on_hand == 7
    log = db.scalars(select(StockAdjustment).order_by(StockAdjustment.id)).all()
    assert [(e.reason, e.quantity_change, e.staff_id) for e in log] == [
        (StockReason.IMPORT, 10, None),
        (StockReason.IMPORT, -3, None),
    ]


def test_any_bad_row_means_nothing_is_imported(db, storage, tmp_path):
    path = write_csv(
        tmp_path,
        "GOOD-1,Good,100,1,,,\n"
        ",No sku,100,1,,,\n"
        "BAD-2,Bad price,abc,1,,,\n"
        "BAD-3,Bad tag,100,1,Birthdayy,,\n"
        "BAD-4,Bad stock,100,-1,,,\n"
        "GOOD-1,Duplicate,100,1,,,\n"
        "BAD-5,Missing photo,100,1,,,nope.jpg\n",
    )

    with pytest.raises(ImportFailed) as failed:
        import_products(db, storage, path, tmp_path)

    errors = "\n".join(failed.value.errors)
    assert "Line 3: sku is required" in errors
    assert "Line 4: price 'abc'" in errors
    assert "Line 5: unknown occasion tag 'Birthdayy'" in errors
    assert "Line 6: on_hand '-1'" in errors
    assert "Line 7: sku GOOD-1 is also on line 2" in errors
    assert "Line 8: image nope.jpg not found" in errors
    assert products_by_sku(db) == {}
    assert storage.files == {}


def test_tags_match_by_name_or_slug_ignoring_case(db, storage, tmp_path):
    path = write_csv(tmp_path, "MUG-1,Mug,100,1,birthday; THANK-YOU,For Her,\n")

    import_products(db, storage, path)

    assert {t.slug for t in products_by_sku(db)["MUG-1"].tags} == {
        "birthday",
        "thank-you",
        "for-her",
    }


def test_non_image_file_is_rejected(db, storage, tmp_path):
    (tmp_path / "notes.png").write_text("not really a picture")
    path = write_csv(tmp_path, "MUG-1,Mug,100,1,,,notes.png\n")

    with pytest.raises(ImportFailed) as failed:
        import_products(db, storage, path, tmp_path)

    assert "JPEG, PNG or WebP" in failed.value.errors[0]


def test_missing_column_is_reported(db, storage, tmp_path):
    path = write_csv(tmp_path, "MUG-1,Mug,1\n", header="sku,name,on_hand\n")

    with pytest.raises(ImportFailed) as failed:
        import_products(db, storage, path)

    assert failed.value.errors == ["Missing column(s): price."]


def test_slug_owned_by_another_product_is_rejected(db, storage, tmp_path):
    import_products(db, storage, write_csv(tmp_path, "MUG-1,Mug,100,1,,,\n"))

    with pytest.raises(ImportFailed) as failed:
        import_products(db, storage, write_csv(tmp_path, "MUG-2,Mug,100,1,,,\n"))

    assert "slug mug already belongs to MUG-1" in failed.value.errors[0]


def test_dry_run_saves_nothing(db, storage):
    summary = import_products(db, storage, SAMPLE_CSV, SAMPLE_IMAGES, dry_run=True)

    assert len(summary.created) == 6
    assert products_by_sku(db) == {}
    assert storage.files == {}


def test_every_imported_stock_level_is_in_the_log(db, storage):
    import_products(db, storage, SAMPLE_CSV, SAMPLE_IMAGES)

    for inventory in db.scalars(select(Inventory)):
        logged = db.scalar(
            select(func.coalesce(func.sum(StockAdjustment.quantity_change), 0)).where(
                StockAdjustment.product_id == inventory.product_id
            )
        )
        assert logged == inventory.on_hand
