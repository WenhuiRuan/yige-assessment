from pathlib import Path
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from app.backend.db import connect, transaction
from app.backend.tests.support import add, assert_error, assert_headers, db_state


def test_api01_product_skus_images_and_empty_cart(client: TestClient) -> None:
    response = client.get("/api/products/p1")
    assert response.status_code == 200
    assert_headers(response)
    product = response.json()
    assert set(product) == {
        "id",
        "name",
        "description",
        "currency",
        "images",
        "options",
        "inventory_revision",
        "skus",
    }
    assert product["id"] == "p1" and product["name"] and product["description"]
    assert product["currency"] == "CNY"
    assert product["options"] == [
        {"name": "color", "values": ["red", "blue"]},
        {"name": "size", "values": ["S", "M", "L", "XL"]},
    ]
    assert product["inventory_revision"] == 0
    skus = product["skus"]
    assert len(skus) == 7
    assert [s["id"] for s in skus] == sorted(s["id"] for s in skus)
    by_id = {s["id"]: s for s in skus}
    assert "sku-blue-xl" not in by_id
    assert by_id["sku-red-l"]["available_quantity"] == 0
    assert by_id["sku-red-xl"]["available_quantity"] == 1
    expected = {
        "sku-red-s": (9900, 5),
        "sku-red-m": (10900, 3),
        "sku-red-l": (11900, 0),
        "sku-red-xl": (12900, 1),
        "sku-blue-s": (9900, 4),
        "sku-blue-m": (10900, 2),
        "sku-blue-l": (11900, 6),
    }
    for sku in skus:
        assert set(sku) == {"id", "price_minor", "available_quantity", "image_url", "option_values"}
        assert (sku["price_minor"], sku["available_quantity"]) == expected[sku["id"]]
        assert sku["option_values"] == {
            "color": sku["id"].split("-")[1],
            "size": sku["id"].split("-")[2].upper(),
        }
    image_paths = [*product["images"], *(sku["image_url"] for sku in skus)]
    assert len(set(image_paths)) == 8
    for path in image_paths:
        image = client.get(path)
        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/svg+xml")
        root = ElementTree.fromstring(image.content)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert root.find("{http://www.w3.org/2000/svg}title") is not None
    cart = client.get("/api/cart")
    assert_headers(cart)
    assert cart.json() == {
        "id": "demo",
        "revision": 0,
        "currency": "CNY",
        "items": [],
        "total_item_count": 0,
        "total_price_minor": 0,
    }


def test_api02_add_merge_amounts_order_and_revisions(client: TestClient, db_path: Path) -> None:
    first = add(client, quantity=2)
    assert first.status_code == 200
    assert_headers(first)
    assert first.json() == {
        "cart": {
            "id": "demo",
            "revision": 1,
            "currency": "CNY",
            "items": [
                {
                    "sku_id": "sku-red-s",
                    "quantity": 2,
                    "unit_price_minor": 9900,
                    "line_total_minor": 19800,
                }
            ],
            "total_item_count": 2,
            "total_price_minor": 19800,
        },
        "inventory": {"revision": 1, "sku_id": "sku-red-s", "available_quantity": 3},
    }
    assert add(client, quantity=1).status_code == 200
    third = add(client, sku="sku-blue-m", quantity=2)
    assert third.status_code == 200
    cart = third.json()["cart"]
    assert [item["sku_id"] for item in cart["items"]] == ["sku-blue-m", "sku-red-s"]
    assert [item["quantity"] for item in cart["items"]] == [2, 3]
    assert cart["total_item_count"] == 5 and cart["total_price_minor"] == 51500
    assert cart["revision"] == 3
    assert client.get("/api/cart").json() == cart
    with connect(db_path) as connection:
        assert connection.execute("SELECT reserved FROM skus WHERE id='sku-red-s'").fetchone() == (
            3,
        )
        assert connection.execute("SELECT revision FROM inventory_meta").fetchone() == (3,)


@pytest.mark.parametrize(
    "quantity", [True, False, "1", 1.0, 0, -1, 2147483648, 10**100, None, [], {}]
)
def test_api03_invalid_quantities_do_not_store_key(
    client: TestClient, db_path: Path, quantity: object
) -> None:
    before = db_state(db_path)
    response = client.post(
        "/api/cart/items",
        json={"sku_id": "sku-red-s", "quantity": quantity},
        headers={"Idempotency-Key": "invalid"},
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert db_state(db_path) == before
    assert add(client, key="invalid").status_code == 200


@pytest.mark.parametrize("sku_id", ["", "x" * 129, "has space", "é", "bad\n", 123, True, None])
def test_api03_invalid_sku_shape(client: TestClient, db_path: Path, sku_id: object) -> None:
    before = db_state(db_path)
    response = client.post(
        "/api/cart/items",
        json={"sku_id": sku_id, "quantity": 1},
        headers={"Idempotency-Key": "invalid"},
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert db_state(db_path) == before


@pytest.mark.parametrize("key", ["", "two words", "\t", "x" * 129, "bad\x7f"])
def test_api03_invalid_key(client: TestClient, db_path: Path, key: str) -> None:
    before = db_state(db_path)
    assert_error(add(client, key=key), 422, "VALIDATION_ERROR")
    assert db_state(db_path) == before


def test_api03_missing_duplicate_and_non_ascii_key(client: TestClient, db_path: Path) -> None:
    before = db_state(db_path)
    payload = {"sku_id": "sku-red-s", "quantity": 1}
    for headers in (
        {},
        [("Idempotency-Key", "one"), ("Idempotency-Key", "two")],
        [(b"Idempotency-Key", b"\xff")],
    ):
        response = client.post("/api/cart/items", json=payload, headers=headers)
        assert_error(response, 422, "VALIDATION_ERROR")
    assert db_state(db_path) == before


@pytest.mark.parametrize(
    "body",
    [
        b"{",
        b"",
        b"null",
        b"[]",
        b"1",
        b"{}",
        b'{"sku_id":"sku-red-s"}',
        b'{"quantity":1}',
        b'{"quantity":' + b"9" * 5000 + b"}",
        b"\xff",
    ],
)
def test_api03_malformed_or_incomplete_json(client: TestClient, db_path: Path, body: bytes) -> None:
    before = db_state(db_path)
    response = client.post(
        "/api/cart/items",
        content=body,
        headers={"Idempotency-Key": "json", "Content-Type": "application/json"},
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert db_state(db_path) == before


@pytest.mark.parametrize(
    "extra", [{"price": 1}, {"stock": 999}, {"secret-field": "sensitive-value"}]
)
def test_api04_untrusted_fields_are_rejected_without_echo(
    client: TestClient, db_path: Path, extra: dict
) -> None:
    before = db_state(db_path)
    response = client.post(
        "/api/cart/items",
        json={"sku_id": "sku-red-s", "quantity": 1, **extra},
        headers={"Idempotency-Key": "forged"},
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert "sensitive-value" not in response.text and "secret-field" not in response.text
    assert db_state(db_path) == before


def test_api03_media_type_and_resource_errors(client: TestClient, db_path: Path) -> None:
    before = db_state(db_path)
    response = client.post(
        "/api/cart/items",
        content='{"sku_id":"sku-red-s","quantity":1}',
        headers={"Content-Type": "text/plain", "Idempotency-Key": "media"},
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert db_state(db_path) == before
    missing = client.get("/api/products/missing")
    assert assert_error(missing, 404, "PRODUCT_NOT_FOUND")["details"] == {"product_id": "missing"}
    sku_missing = add(client, sku="missing", key="sku-missing")
    assert assert_error(sku_missing, 404, "SKU_NOT_FOUND")["details"] == {"sku_id": "missing"}


def test_api05_canonical_payload_and_historical_success_replay(
    client: TestClient, db_path: Path
) -> None:
    first = add(client, quantity=2, key="same")
    assert first.status_code == 200
    before = db_state(db_path)
    replay = client.post(
        "/api/cart/items",
        content='{"quantity":2,"sku_id":"sku-red-s"}',
        headers={"Content-Type": "application/json", "Idempotency-Key": "same"},
    )
    assert replay.status_code == 200 and replay.content == first.content
    assert first.headers["X-Request-ID"] != replay.headers["X-Request-ID"]
    assert db_state(db_path) == before
    assert add(client, sku="sku-blue-s", key="new").status_code == 200
    current = db_state(db_path)
    old = add(client, quantity=2, key="same")
    assert old.content == first.content
    assert old.json()["cart"]["revision"] == 1
    assert client.get("/api/cart").json()["revision"] == 2
    assert db_state(db_path) == current


def test_api06_conflict_and_validation_priority_preserve_original(
    client: TestClient, db_path: Path
) -> None:
    first = add(client, key="same")
    assert first.status_code == 200
    before = db_state(db_path)
    assert_error(add(client, quantity=2, key="same"), 409, "IDEMPOTENCY_CONFLICT")
    assert_error(add(client, sku="sku-blue-s", key="same"), 409, "IDEMPOTENCY_CONFLICT")
    assert_error(add(client, quantity=0, key="same"), 422, "VALIDATION_ERROR")
    assert db_state(db_path) == before
    assert add(client, key="same").content == first.content


@pytest.mark.parametrize("kind", ["stock", "sku"])
def test_api07_failed_result_persists_after_business_state_changes(
    client: TestClient, db_path: Path, kind: str
) -> None:
    sku = "sku-red-l" if kind == "stock" else "sku-blue-xl"
    status, code = (409, "INSUFFICIENT_STOCK") if kind == "stock" else (404, "SKU_NOT_FOUND")
    first = add(client, sku=sku, key="refused")
    error = assert_error(first, status, code)
    assert error["request_id"] == first.headers["X-Request-ID"]
    with connect(db_path) as connection, transaction(connection, "IMMEDIATE"):
        if kind == "stock":
            connection.execute("UPDATE skus SET on_hand = 2 WHERE id = ?", (sku,))
        else:
            connection.execute(
                "INSERT INTO skus VALUES "
                "(?, 'p1', 'blue', 'XL', 12900, 2, 0, '/images/product.svg')",
                (sku,),
            )
        connection.execute("UPDATE inventory_meta SET revision = revision + 1")
    changed = db_state(db_path)
    replay = add(client, sku=sku, key="refused")
    assert_error(replay, status, code)
    assert replay.content == first.content
    assert replay.headers["X-Request-ID"] != error["request_id"]
    assert replay.json()["error"]["request_id"] == error["request_id"]
    assert db_state(db_path) == changed
    assert add(client, sku=sku, key="new-intention").status_code == 200


def test_api05_keys_are_case_sensitive(client: TestClient, db_path: Path) -> None:
    assert add(client, key="CaseSensitive").status_code == 200
    second = add(client, key="casesensitive")
    assert second.status_code == 200
    assert second.json()["cart"]["total_item_count"] == 2
    with connect(db_path) as connection:
        assert connection.execute("SELECT count(*) FROM idempotency_records").fetchone() == (2,)
