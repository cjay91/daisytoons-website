# Part 2 spec: data model, auth and core API

Goal: the database and the security model everything else builds on.

Done when: migrations run cleanly on a fresh database (up, down and up again), and role checks are covered by tests (a packer cannot change prices).

## Tables

Money is stored as `NUMERIC(10, 2)` in the shop's single currency. Every table has `created_at` and `updated_at`.

| Table | Main columns | Notes |
| --- | --- | --- |
| `customers` | email (unique), password_hash, full_name, phone, is_active | Email is stored lowercase. |
| `addresses` | customer_id, label, recipient_name, line1, line2, city, region, postal_code, country, phone, is_default | A customer has many. |
| `staff` | email (unique), password_hash, full_name, role, is_active | role is `admin`, `packer` or `support`. |
| `products` | sku (unique), slug (unique), name, description, price, is_active | Images and occasion/recipient tags come in Part 3. |
| `inventory` | product_id (one row per product), on_hand, reserved, reorder_point, bin_location | The adjustment log comes in Part 3. |
| `orders` | order_number (unique), customer_id (empty for guests), email, status, subtotal, delivery_fee, total, shipping_address, notes | shipping_address is a copy of the address at order time, so later edits don't change old orders. |
| `order_items` | order_id, product_id, product_name, unit_price, quantity, line_total | Name and price are copied at order time. |
| `suppliers` | name, email, phone, notes | |
| `purchase_orders` | supplier_id, status, expected_at, notes | status is `draft`, `sent`, `received` or `cancelled`. |
| `purchase_order_items` | purchase_order_id, product_id, quantity, unit_cost | |

Order status values are `pending`, `paid`, `packing`, `shipped`, `delivered`, `cancelled` and `refunded`. The rules for moving between them are Part 4.

## Login

- Passwords are hashed with Argon2 and never stored or logged in plain text. Minimum length is 8.
- Logging in returns a signed token (JWT) that the app sends as `Authorization: Bearer <token>`. Tokens last 60 minutes.
- A token says who it is for: a customer or a staff member. A customer token never works on staff endpoints, and the other way round.
- Wrong email and wrong password give the same error, so the API doesn't reveal which emails exist.
- The first admin is created from the command line: `python -m app.cli create-admin`. After that, admins create other staff through the API.

## Endpoints

| Method and path | Who can call it |
| --- | --- |
| `POST /auth/register` | Anyone (creates a customer) |
| `POST /auth/login` | Anyone (customer login) |
| `GET /me` | Logged-in customer |
| `POST /staff/auth/login` | Anyone (staff login) |
| `GET /staff/me` | Any staff member |
| `GET /staff/members`, `POST /staff/members` | Admin |
| `GET /products`, `GET /products/{slug}` | Anyone (active products only) |
| `POST /staff/products` | Admin |
| `PATCH /staff/products/{id}` | Admin (details and price) |
| `GET /staff/products/{id}/inventory` | Any staff member |
| `PATCH /staff/products/{id}/inventory` | Admin, packer |

## Roles

| Action | admin | packer | support |
| --- | --- | --- | --- |
| Manage staff accounts | yes | no | no |
| Create products, change prices and details | yes | no | no |
| Change stock (on hand, reorder point, bin) | yes | yes | no |
| View products and stock | yes | yes | yes |

Order, customer and supplier permissions arrive with their endpoints in later parts and follow the same pattern.

## Errors

Every error has the same shape:

```json
{"error": {"code": "forbidden", "message": "Your role cannot change prices."}}
```

Codes used so far: `validation_error` (422), `invalid_credentials` (401), `not_authenticated` (401), `forbidden` (403), `not_found` (404), `conflict` (409, for example an email or SKU that already exists).

## Code layout

- `app/models/`: SQLAlchemy models, one file per area.
- `app/services/`: business rules. Routes call services; services raise app errors.
- `app/api/`: thin routes plus the auth dependencies that check tokens and roles.
- `migrations/`: Alembic. The API container runs `alembic upgrade head` on start.
