"""Every public GET builds its full snapshot in a single read transaction."""

import json
import sqlite3
from pathlib import Path

from app.backend.db import connect, transaction
from app.backend.errors import ApiError
from app.backend.schemas import Cart, CartItem, Product, Sku


def inventory_revision(connection: sqlite3.Connection) -> int:
    return connection.execute("SELECT revision FROM inventory_meta WHERE id = 1").fetchone()[0]


def _read_skus(connection: sqlite3.Connection, product_id: str) -> list[Sku]:
    return [
        Sku(
            id=row[0],
            price_minor=row[1],
            available_quantity=row[2] - row[3],
            image_url=row[4],
            option_values={"color": row[5], "size": row[6]},
        )
        for row in connection.execute(
            "SELECT id, price_minor, on_hand, reserved, image_url, color, size "
            "FROM skus WHERE product_id = ? ORDER BY id",
            (product_id,),
        )
    ]


def get_product(path: Path, product_id: str, timeout: float = 5.0) -> Product:
    with connect(path, timeout) as connection, transaction(connection):
        row = connection.execute(
            "SELECT id, name, description, currency, images_json, options_json "
            "FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row is None:
            raise ApiError(
                404, "PRODUCT_NOT_FOUND", "Product not found", {"product_id": product_id}
            )
        skus = _read_skus(connection, product_id)
        return Product(
            id=row[0],
            name=row[1],
            description=row[2],
            currency=row[3],
            images=json.loads(row[4]),
            options=json.loads(row[5]),
            inventory_revision=inventory_revision(connection),
            skus=skus,
        )


def _read_cart_items(connection: sqlite3.Connection) -> list[CartItem]:
    return [
        CartItem(
            sku_id=row[0],
            quantity=row[1],
            unit_price_minor=row[2],
            line_total_minor=row[1] * row[2],
        )
        for row in connection.execute(
            "SELECT c.sku_id, c.quantity, s.price_minor FROM cart_items c "
            "JOIN skus s ON s.id = c.sku_id WHERE c.cart_id = 'demo' ORDER BY c.sku_id"
        )
    ]


def cart_snapshot(connection: sqlite3.Connection) -> Cart:
    revision = connection.execute("SELECT revision FROM carts WHERE id = 'demo'").fetchone()[0]
    items = _read_cart_items(connection)
    return Cart(
        id="demo",
        revision=revision,
        currency="CNY",
        items=items,
        total_item_count=sum(item.quantity for item in items),
        total_price_minor=sum(item.line_total_minor for item in items),
    )


def get_cart(path: Path, timeout: float = 5.0) -> Cart:
    with connect(path, timeout) as connection, transaction(connection):
        return cart_snapshot(connection)
