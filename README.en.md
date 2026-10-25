# Yige Full-Stack Assessment

[中文版](README.md)

- [A](A/README.en.md): inventory reservation program, complexity analysis, and tests.
- [B](B/README.en.md): multi-warehouse allocation program, algorithm explanation, and tests.
- [C](C/answers.en.md): answers to the six Xero integration questions.
- `app/`: FastAPI backend and React/TypeScript product page.

## Setup and run

Requires Python 3.11+, Node 24.x (≥24.15), and npm ≥10. Verified on Windows with Python 3.12.10, Node 24.18.0, and npm 10.5.0.

Main dependencies: FastAPI, Pydantic, Uvicorn; React, TypeScript, Vite. Tests use pytest/HTTPX, Vitest/Testing Library/MSW, and Playwright. SQLite is provided by the Python standard library. See `requirements-dev.txt` and `app/frontend/package-lock.json` for versions.

In the first PowerShell terminal, run from the repository root:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, start from the repository root:

```powershell
cd app/frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Open the [product page](http://127.0.0.1:5173). The [API documentation](http://127.0.0.1:8000/docs) is available for debugging. Press Ctrl+C to stop a service. In Bash, use `.venv/bin/python` and `npm`; other operating systems have not been tested.

Startup creates the tables and seeds product p1: two colors (red/blue), four sizes (S/M/L/XL), and seven SKUs. Blue XL is an absent combination; red L is sold out. Data is stored in `data/yige.sqlite3` and survives restarts. To clear demo records, stop the backend, run `.venv/Scripts/python.exe -m app.backend.seed --reset` from the repository root, restart the backend, and reload the page.

Environment variables: `YIGE_DB_PATH` sets the database path; `YIGE_API_TARGET` sets the frontend proxy target (default: `http://127.0.0.1:8000`). `.env.example` is documentation only; .env files are not loaded automatically.

## Tests

Install the Python and frontend dependencies above, then open a new terminal. Run the A, B, and backend tests from the repository root.

**A: Inventory reservation program.** Tests reservation, release, shipping, restocking, stock and order boundaries, invalid input, event replay, and large inputs.

```powershell
.venv/Scripts/python.exe -m pytest A/tests -q
```

**B: Multi-warehouse allocation algorithm.** Tests the minimum warehouse count and cost, lexicographic tie-breaking, infeasible cases, zero demand, and large inputs.

```powershell
.venv/Scripts/python.exe -m pytest B/tests -q
```

**C: Written Xero answers.** See [C/answers.en.md](C/answers.en.md); there are no automated tests for this part.

**Application backend.** Tests API parameters and error responses, cart totals, idempotent replay, concurrent overselling prevention, transaction rollback, and persistence across restarts.

```powershell
.venv/Scripts/python.exe -m pytest app/backend/tests -q
```

To run all Python tests for A, B, and the backend together, use the following instead of the three individual commands; there is no need to run both:

```powershell
.venv/Scripts/python.exe -m pytest -q
```

**Frontend tests.** From the repository root, enter the frontend directory. Tests cover image, price, and stock updates when variants change; absent and sold-out combinations; quantity limits; duplicate submission prevention; loading failures; timeout retries; and stale responses.

```powershell
cd app/frontend
npm.cmd run test -- --run
```

**End-to-end tests.** Continue in the frontend directory. Chromium connects to a real backend to test variant selection and adding to the cart, retries after a lost response, recovery when another request takes the last unit, and layout and keyboard interaction at 375px and 1280px. Tests automatically start isolated services using a temporary SQLite database and ports 18000/15173.

```powershell
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

**Code checks and build.** Ruff and ESLint check code quality; typecheck checks TypeScript types; build verifies that the frontend production build completes.

From the repository root:

```powershell
.venv/Scripts/python.exe -m ruff check .
```

From the frontend directory:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

## API examples

Amounts are integer CNY minor units (fen). The cart item count is the sum of item quantities. The examples below use the initial data. The Chinese description in the product response is retained as returned by the API.

**GET /api/products/p1 → 200.** No request body. Response excerpt (the full response contains seven SKUs; only one is shown):

```json
{
  "id": "p1",
  "name": "Variant Demo Tee",
  "description": "用于规格选择和库存预留演示的 T 恤",
  "currency": "CNY",
  "images": ["/images/product.svg"],
  "options": [
    {"name": "color", "values": ["red", "blue"]},
    {"name": "size", "values": ["S", "M", "L", "XL"]}
  ],
  "inventory_revision": 0,
  "skus": [
    {"id": "sku-red-s", "price_minor": 9900, "available_quantity": 5,
     "image_url": "/images/sku-red-s.svg", "option_values": {"color": "red", "size": "S"}}
  ]
}
```

**POST /api/cart/items.** Accepts only sku_id and a positive integer quantity. Price and stock are determined by the server:

```http
POST /api/cart/items
Content-Type: application/json
Idempotency-Key: example-1

{"sku_id":"sku-red-s","quantity":1}
```

First successful response, **200**:

```json
{
  "cart": {
    "id":"demo","revision":1,"currency":"CNY",
    "items":[{"sku_id":"sku-red-s","quantity":1,"unit_price_minor":9900,"line_total_minor":9900}],
    "total_item_count":1,"total_price_minor":9900
  },
  "inventory":{"revision":1,"sku_id":"sku-red-s","available_quantity":4}
}
```

**GET /api/cart → 200.** No request body. Response after the addition above:

```json
{
  "id":"demo","revision":1,"currency":"CNY",
  "items":[{"sku_id":"sku-red-s","quantity":1,"unit_price_minor":9900,"line_total_minor":9900}],
  "total_item_count":1,"total_price_minor":9900
}
```

| Status code | Meaning |
| --- | --- |
| 200 | Successful read or cart addition; replaying the same key and payload returns the original business result |
| 404 | Product or SKU does not exist |
| 409 | Insufficient stock, or the same key is used for a different request |
| 422 | Invalid JSON, fields, quantity, or idempotency key; client-supplied price/stock is not accepted |
| 500 / 503 | Unexpected error / database temporarily unavailable |

Errors consistently use an `error` object. For example, insufficient stock:

```json
{
  "error": {
    "code":"INSUFFICIENT_STOCK","message":"Requested quantity exceeds available stock",
    "details":{"sku_id":"sku-red-xl","requested_quantity":2,"available_quantity":1,"inventory_revision":0},
    "request_id":"example-request-id"
  }
}
```

Idempotency keys contain 1–128 non-whitespace printable ASCII characters. Normal business responses include `X-Request-ID` and `Cache-Control: no-store`. The same key does not add items twice; changing the request content requires a new operation.

## Architecture, assumptions, and limitations

- The backend separates routes, services, and data access, with a separate SQLite connection for each request. Adding to the cart reserves stock: on-hand quantity stays unchanged while availability decreases. A conditional stock UPDATE inside a `BEGIN IMMEDIATE` transaction prevents overselling. Cart changes, revisions, and idempotency results commit together; failures roll back the whole transaction.
- Successful results and definitive SKU-not-found/insufficient-stock results are persisted. Malformed requests and 500/503 responses are not cached. Reusing a key with a different valid request returns 409.
- The frontend separates API access, domain logic, and UI. A synchronous submission lock prevents double clicks. Cart and inventory revisions are tracked independently, so stale responses cannot overwrite newer state. Timeouts and lost responses retain the original key/payload for retry. If a read fails after a successful addition, only the read is retried.
- There is one shared demo cart, without user isolation, reservation release, or expiry. Idempotency records are not cleaned up; SQLite permits only one writer at a time. Unconfirmed operations are kept only in the current page's memory; closing the page before confirmation loses that retry context.
- Authentication, checkout, payments, and production deployment are outside the implemented scope. Optional optimistic UI, analytics events, and containerization are not implemented.

## AI usage disclosure

For the full-stack application, AI assisted with setting up the FastAPI and React/TypeScript projects and writing routine endpoints, page components, and styles.

During testing and delivery, AI assisted with writing and extending automated tests and organizing the documentation. I checked that the commands, explanations, and code were consistent.
