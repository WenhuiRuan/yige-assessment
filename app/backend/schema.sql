BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS app_meta (
    name TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO app_meta(name, value) VALUES ('schema_stage', 'P0');

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    currency TEXT NOT NULL CHECK (currency = 'CNY'),
    options_json TEXT NOT NULL,
    images_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skus (
    id TEXT PRIMARY KEY NOT NULL,
    product_id TEXT NOT NULL REFERENCES products(id),
    color TEXT NOT NULL,
    size TEXT NOT NULL,
    price_minor INTEGER NOT NULL CHECK (typeof(price_minor) = 'integer' AND price_minor >= 0),
    on_hand INTEGER NOT NULL,
    reserved INTEGER NOT NULL DEFAULT 0,
    image_url TEXT NOT NULL,
    UNIQUE (product_id, color, size),
    CHECK (typeof(on_hand) = 'integer' AND on_hand >= 0
           AND typeof(reserved) = 'integer' AND reserved >= 0 AND reserved <= on_hand)
);
CREATE TABLE IF NOT EXISTS carts (
    id TEXT PRIMARY KEY NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0 CHECK (typeof(revision) = 'integer' AND revision >= 0)
);
CREATE TABLE IF NOT EXISTS cart_items (
    cart_id TEXT NOT NULL REFERENCES carts(id),
    sku_id TEXT NOT NULL REFERENCES skus(id),
    quantity INTEGER NOT NULL CHECK (typeof(quantity) = 'integer' AND quantity > 0),
    PRIMARY KEY (cart_id, sku_id)
);
CREATE TABLE IF NOT EXISTS idempotency_records (
    cart_id TEXT NOT NULL REFERENCES carts(id),
    operation TEXT NOT NULL,
    key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status_code INTEGER NOT NULL CHECK (status_code IN (200, 404, 409)),
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (cart_id, operation, key)
);
CREATE TABLE IF NOT EXISTS inventory_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revision INTEGER NOT NULL DEFAULT 0 CHECK (typeof(revision) = 'integer' AND revision >= 0)
);
COMMIT;
