# Daisytoons website

The gift shop website, kept in one repository with two parts.

## Layout

```
daisytoons-website/
├── frontend/   Storefront the customers use: browsing, cart, checkout
├── backend/    API, orders, payments, inventory and other business logic
├── docs/       Project documents, including the build plan
└── README.md   This file
```

- **frontend/** talks to the backend only through its API. It never reaches the database directly.
- **backend/** owns the data and the rules: products, stock, orders and payment handling. Card details are taken by the payment gateway's hosted checkout page, never by our servers.

## Status

Skeleton only. No frameworks or tooling have been picked yet; each folder will get its own setup instructions once they are.

See `docs/Gift Shop Build Plan.pdf` for the full build plan.
