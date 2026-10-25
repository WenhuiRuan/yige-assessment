import sqlite3
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from app.backend.db import connect
from app.backend.main import create_app
from app.backend.services import cart, reads
from app.backend.tests.support import add, assert_error, db_state


@pytest.mark.parametrize("stage", ["after-stock", "after-cart", "before-idempotency"])
def test_api11_real_sql_changes_roll_back_at_each_stage(
    client: TestClient, db_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    before = db_state(db_path)
    function = {
        "after-stock": "_reserve_stock",
        "after-cart": "_add_cart_line",
        "before-idempotency": "_store_result",
    }[stage]
    original = getattr(cart, function)
    reached = []

    def fail(connection, *args, **kwargs):
        if stage != "before-idempotency":
            original(connection, *args, **kwargs)  # Execute the real conditional update/cart SQL.
        assert connection.in_transaction
        assert connection.execute("SELECT reserved FROM skus WHERE id='sku-red-s'").fetchone() == (
            1,
        )
        if stage != "after-stock":
            assert connection.execute("SELECT quantity FROM cart_items").fetchone() == (1,)
        if stage == "before-idempotency":
            assert connection.execute("SELECT revision FROM inventory_meta").fetchone() == (1,)
            assert connection.execute("SELECT revision FROM carts").fetchone() == (1,)
        reached.append(stage)
        raise RuntimeError("private SQL secret-input C:/internal/path")

    with monkeypatch.context() as patch:
        patch.setattr(cart, function, fail)
        response = add(client, key="rollback")
        error = assert_error(response, 500, "INTERNAL_ERROR")
        assert error["request_id"] == response.headers["X-Request-ID"]
        assert all(
            value not in response.text for value in ("private", "secret-input", "C:/internal")
        )
    assert reached == [stage]
    assert db_state(db_path) == before
    assert add(client, key="rollback").status_code == 200
    with connect(db_path) as connection:
        assert connection.execute("SELECT reserved FROM skus WHERE id='sku-red-s'").fetchone() == (
            1,
        )
        assert connection.execute("SELECT count(*) FROM idempotency_records").fetchone() == (1,)
    print(
        f"\nAPI11 {stage}: real uncommitted changes observed; all six tables restored; retry once"
    )


def test_api14_real_database_lock_timeout_is_retryable(db_path: Path) -> None:
    with TestClient(create_app(db_path, busy_timeout_seconds=0.05)) as client:
        before = db_state(db_path)
        with connect(db_path) as locker:
            locker.execute("BEGIN IMMEDIATE")
            started = perf_counter()
            response = add(client, key="locked")
            elapsed = perf_counter() - started
            assert_error(response, 503, "TEMPORARILY_UNAVAILABLE")
            locker.rollback()
        assert db_state(db_path) == before
        assert add(client, key="locked").status_code == 200
    print(
        f"\nAPI14: actual SQLite writer lock, timeout=0.05s, response after {elapsed:.4f}s"
    )


@pytest.mark.parametrize("exception", [RuntimeError, sqlite3.OperationalError])
def test_api14_unknown_failure_is_sanitized_and_request_ids_are_generated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, exception
) -> None:
    secret = "secret-token SELECT * FROM private_table C:/internal/path"

    def fail(*_args):
        raise exception(secret)

    monkeypatch.setattr(reads, "_read_skus", fail)
    response = client.get("/api/products/p1", headers={"X-Request-ID": "untrusted-sensitive-id"})
    error = assert_error(response, 500, "INTERNAL_ERROR")
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert error["request_id"] != "untrusted-sensitive-id"
    for value in (secret, "untrusted-sensitive-id", "private_table", "Traceback"):
        assert value not in response.text and value not in caplog.text
