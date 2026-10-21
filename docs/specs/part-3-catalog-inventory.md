# Part 3 spec: catalog and inventory

Goal: the ~100 products live in the system with accurate stock.

Done when: all products are imported with stock levels, and every stock change is logged.

## Tables

| Table | Main columns | Notes |
| --- | --- | --- |
| `tags` | kind, slug, name | kind is `occasion` or `recipient`. Unique per kind and slug. A starter set is created by the migration. |
| `product_tags` | product_id, tag_id | Links products and tags (many to many). |
| `product_images` | product_id, storage_key, original_filename, alt_text, position, content_type | The image file itself lives in object storage; this row points at it. position 0 is the main photo. |
| `stock_adjustments` | product_id, staff_id, reason, quantity_change, on_hand_before, on_hand_after, note, created_at | One row per stock change. staff_id is empty for changes made by the import script. Rows are never edited or deleted. |

Starter tags:

- Occasions: Birthday, Anniversary, Wedding, Valentine's Day, Avurudu, Christmas, Mother's Day, Father's Day, Graduation, New baby, Thank you, Get well soon.
- Recipients: For her, For him, For kids, For couples, For parents, For friends, For teachers, For colleagues.

Stock adjustment reasons: `received` (a delivery), `count` (a stock count), `damaged`, `returned`, `correction`, `import`.

## The stock rule

Stock on hand changes in exactly one place: the stock adjustment service. It writes the new number and the log row in the same database transaction, so one can't happen without the other. The old "set on_hand" field is removed from the inventory edit endpoint, which now changes only the reorder point and bin location.

An adjustment is either a change (`quantity_change: 12` for 12 received) or a count (`new_on_hand: 37` after counting the shelf). Stock can't go below zero or below what's reserved.

## Images

- Uploads accept JPEG, PNG or WebP up to 5 MB. The file's first bytes are checked, not just its name.
- Files are stored as `products/<product id>/<random id>.<ext>` in an S3-compatible bucket, so names never clash and can't be guessed from the product.
- Locally, Docker Compose runs SeaweedFS as the S3-compatible store. The live shop will use a hosted provider (picked in Part 7); only settings change.
- Product responses include each image's public URL.

## Endpoints

| Method and path | Who |
| --- | --- |
| `GET /products?occasion=birthday&recipient=for-her` | Anyone; filters are optional and combine |
| `GET /tags` | Anyone |
| `POST /staff/tags` | Admin |
| `PUT /staff/products/{id}/tags` | Admin (replaces the product's tags) |
| `POST /staff/products/{id}/images` | Admin (file upload) |
| `PATCH /staff/products/{id}/images/{image_id}`, `DELETE ...` | Admin (alt text, order, remove) |
| `POST /staff/products/{id}/stock-adjustments` | Admin, packer |
| `GET /staff/products/{id}/stock-adjustments` | Any staff |
| `PATCH /staff/products/{id}/inventory` | Admin, packer (reorder point, bin only) |

Archiving a product is `PATCH /staff/products/{id}` with `is_active: false`; it then disappears from the storefront but keeps its history.

## Import

`python -m app.cli import-products products.csv --images ./photos [--dry-run]`

The template is `docs/templates/products-template.csv`. One row per product:

| Column | Required | Example |
| --- | --- | --- |
| sku | yes | `MUG-001` |
| name | yes | `Daisy mug` |
| slug | no (made from the name) | `daisy-mug` |
| description | no | |
| price | yes, in LKR | `1250.00` |
| occasions | no, separated by `;` | `Birthday; Thank you` |
| recipients | no, separated by `;` | `For her; For friends` |
| on_hand | yes | `24` |
| reorder_point | no (default 0) | `5` |
| bin_location | no | `A-3` |
| images | no, file names in the images folder, separated by `;`, main photo first | `mug-front.jpg; mug-side.jpg` |
| active | no (default yes) | `yes` or `no` |

Rules:

- Every row is checked first. If any row has a problem (a missing price, an unknown tag, a missing photo file), nothing is imported and every problem is listed with its row number.
- Products are matched by SKU, so running the import again updates them instead of making duplicates.
- Stock from the file is applied as an `import` adjustment, only when it differs from the current stock, so re-running doesn't create noise in the log.
- A photo already attached to the product (same file name) isn't uploaded again.
- `--dry-run` checks the file and reports what would change without saving anything.
