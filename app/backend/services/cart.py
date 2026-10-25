"""Reserve stock and persist the entire idempotent business result atomically."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.backend.db import connect, transaction
from app.backend.errors import ApiError, encode_body
from app.backend.schemas import AddCartItemRequest, AddCartItemResponse, InventoryUpdate
from app.backend.services.reads import cart_snapshot, inventory_revision

OPERATION = "POST /api/cart/items"


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status: int
    body: str


def _reserve_stock(connection: sqlite3.Connection, sku_id: str, quantity: int) -> int:
    return connection.execute(
        "UPDATE skus SET reserved = reserved + :qty "
        "WHERE id = :sku_id AND on_hand - reserved >= :qty",
        {"sku_id": sku_id, "qty": quantity},
    ).rowcount


def _add_cart_line(connection: sqlite3.Connection, sku_id: str, quantity: int) -> None:
    connection.execute(
        "INSERT INTO cart_items VALUES ('demo', ?, ?) "
        "ON CONFLICT(cart_id, sku_id) DO UPDATE "
        "SET quantity = cart_items.quantity + excluded.quantity",
        (sku_id, quantity),
    )


def _store_result(
    connection: sqlite3.Connection, key: str, request_hash: str, result: StoredResponse
) -> None:
    connection.execute(
        "INSERT INTO idempotency_records "
        "(cart_id, operation, key, request_hash, status_code, response_json) "
        "VALUES ('demo', ?, ?, ?, ?, ?)",
        (OPERATION, key, request_hash, result.status, result.body),
    )


def add_item(
    path: Path, payload: AddCartItemRequest, key: str, request_id: str, timeout: float = 5.0
) -> StoredResponse:
    canonical = json.dumps(payload.model_dump(), sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with connect(path, timeout) as connection, transaction(connection, "IMMEDIATE"):
        previous = connection.execute(
            "SELECT request_hash, status_code, response_json FROM idempotency_records "
            "WHERE cart_id = 'demo' AND operation = ? AND key = ?",
            (OPERATION, key),
        ).fetchone()
        if previous is not None:
            if previous[0] != request_hash:
                raise ApiError(
                    409, "IDEMPOTENCY_CONFLICT", "Key already used for a different request"
                )
            return StoredResponse(previous[1], previous[2])

        sku = connection.execute(
            "SELECT on_hand, reserved FROM skus WHERE id = ?",
            (payload.sku_id,),
        ).fetchone()
        if sku is None:
            error = ApiError(404, "SKU_NOT_FOUND", "SKU not found", {"sku_id": payload.sku_id})
            result = StoredResponse(404, encode_body(error.body(request_id)))
        elif _reserve_stock(connection, payload.sku_id, payload.quantity) == 0:
            error = ApiError(
                409,
                "INSUFFICIENT_STOCK",
                "Requested quantity exceeds available stock",
                {
                    "sku_id": payload.sku_id,
                    "requested_quantity": payload.quantity,
                    "available_quantity": sku[0] - sku[1],
                    "inventory_revision": inventory_revision(connection),
                },
            )
            result = StoredResponse(409, encode_body(error.body(request_id)))
        else:
            _add_cart_line(connection, payload.sku_id, payload.quantity)
            connection.execute("UPDATE carts SET revision = revision + 1 WHERE id = 'demo'")
            connection.execute("UPDATE inventory_meta SET revision = revision + 1 WHERE id = 1")
            available = connection.execute(
                "SELECT on_hand - reserved FROM skus WHERE id = ?",
                (payload.sku_id,),
            ).fetchone()[0]
            response = AddCartItemResponse(
                cart=cart_snapshot(connection),
                inventory=InventoryUpdate(
                    revision=inventory_revision(connection),
                    sku_id=payload.sku_id,
                    available_quantity=available,
                ),
            )
            result = StoredResponse(200, encode_body(response.model_dump(mode="json")))
        _store_result(connection, key, request_hash, result)
        return result
