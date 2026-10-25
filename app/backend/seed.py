"""Idempotent seed and an explicitly requested development-only business reset."""

import argparse
import json
from pathlib import Path

from app.backend.db import connect, database_path, initialize_database, transaction

SKU_SEED = (
    ("red", "S", 9900, 5),
    ("red", "M", 10900, 3),
    ("red", "L", 11900, 0),
    ("red", "XL", 12900, 1),
    ("blue", "S", 9900, 4),
    ("blue", "M", 10900, 2),
    ("blue", "L", 11900, 6),
)


def seed_database(path: Path, *, reset: bool = False, timeout: float = 5.0) -> None:
    initialize_database(path, timeout)
    with connect(path, timeout) as connection, transaction(connection, "IMMEDIATE"):
        if reset:
            for table in (
                "idempotency_records",
                "cart_items",
                "skus",
                "carts",
                "products",
                "inventory_meta",
            ):
                connection.execute(f"DELETE FROM {table}")
        connection.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
            (
                "p1",
                "Variant Demo Tee",
                "用于规格选择和库存预留演示的 T 恤",
                "CNY",
                json.dumps(
                    [
                        {"name": "color", "values": ["red", "blue"]},
                        {"name": "size", "values": ["S", "M", "L", "XL"]},
                    ]
                ),
                json.dumps(["/images/product.svg"]),
            ),
        )
        for color, size, price, stock in SKU_SEED:
            sku_id = f"sku-{color}-{size.lower()}"
            connection.execute(
                "INSERT INTO skus "
                "(id, product_id, color, size, price_minor, on_hand, reserved, image_url) "
                "VALUES (?, 'p1', ?, ?, ?, ?, 0, ?) ON CONFLICT(id) DO NOTHING",
                (sku_id, color, size, price, stock, f"/images/{sku_id}.svg"),
            )
        connection.execute("INSERT INTO carts VALUES ('demo', 0) ON CONFLICT(id) DO NOTHING")
        connection.execute("INSERT INTO inventory_meta VALUES (1, 0) ON CONFLICT(id) DO NOTHING")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="Override YIGE_DB_PATH for this command")
    parser.add_argument(
        "--reset", action="store_true", help="Clear and reseed all demo business data"
    )
    args = parser.parse_args()
    path = args.db if args.db is not None else database_path()
    seed_database(path, reset=args.reset)
    print(
        "Demo business data reset and seeded"
        if args.reset
        else "Demo data seeded without overwrite"
    )


if __name__ == "__main__":
    main()
