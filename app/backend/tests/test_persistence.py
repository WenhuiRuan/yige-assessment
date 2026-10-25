import sqlite3
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.backend.db import connect
from app.backend.main import create_app
from app.backend.seed import seed_database
from app.backend.tests.support import ROOT, add, db_state, live_server


class DropCommittedResponse(httpx.BaseTransport):
    """Real HTTP delegate; discard the received response before returning it to the caller."""

    def __init__(self) -> None:
        self.delegate = httpx.HTTPTransport()
        self.observed: tuple[int, bytes] | None = None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.delegate.handle_request(request)
        self.observed = response.status_code, response.read()
        response.close()
        raise httpx.ReadError("Test transport discarded the committed response", request=request)

    def close(self) -> None:
        self.delegate.close()


def test_api12_lost_real_http_response_recovers_without_second_add(
    application: FastAPI, db_path: Path
) -> None:
    transport = DropCommittedResponse()
    with live_server(application) as url:
        with httpx.Client(base_url=url, transport=transport, timeout=10) as client:
            with pytest.raises(httpx.ReadError):
                add(client, quantity=2, key="lost-response")
        assert transport.observed is not None and transport.observed[0] == 200
        committed = db_state(db_path)
        with httpx.Client(base_url=url, timeout=10) as client:
            replay = add(client, quantity=2, key="lost-response")
            assert replay.status_code == 200
            assert replay.content == transport.observed[1]
            assert client.get("/api/cart").json()["total_item_count"] == 2
        assert db_state(db_path) == committed
        with connect(db_path) as connection:
            assert connection.execute("SELECT sum(reserved) FROM skus").fetchone() == (2,)
            assert connection.execute("SELECT revision FROM inventory_meta").fetchone() == (1,)
            assert connection.execute("SELECT count(*) FROM idempotency_records").fetchone() == (1,)
    print(
        "\nAPI12: real server 200 discarded before caller received it; replay 200 byte-identical; "
        "cart/reserved=2, revision=1, one stored operation"
    )


def test_api13_server_restart_keeps_cart_inventory_and_replay(db_path: Path) -> None:
    with live_server(create_app(db_path)) as first_url:
        with httpx.Client(base_url=first_url, timeout=10) as client:
            response = add(client, quantity=2, key="restart")
            assert response.status_code == 200
        committed = db_state(db_path)
    with live_server(create_app(db_path)) as second_url:
        assert db_state(db_path) == committed
        with httpx.Client(base_url=second_url, timeout=10) as client:
            replay = add(client, quantity=2, key="restart")
            assert replay.status_code == 200 and replay.content == response.content
            assert client.get("/api/cart").json()["total_item_count"] == 2
            sku = next(
                s for s in client.get("/api/products/p1").json()["skus"] if s["id"] == "sku-red-s"
            )
            assert sku["available_quantity"] == 3
        assert db_state(db_path) == committed
    print("\nAPI13: old HTTP server stopped; fresh app/server on same file preserves exact replay")


def test_p0_database_migrates_without_deleting_existing_metadata(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE app_meta (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.executemany(
            "INSERT INTO app_meta VALUES (?, ?)", [("schema_stage", "P0"), ("sentinel", "keep")]
        )
    with TestClient(create_app(db_path)) as client:
        assert client.get("/api/health").json() == {
            "status": "ok",
            "database": "sqlite",
            "stage": "P0",
        }
        assert len(client.get("/api/products/p1").json()["skus"]) == 7
        assert client.get("/api/cart").json()["items"] == []
    with connect(db_path) as connection:
        assert connection.execute(
            "SELECT value FROM app_meta WHERE name='sentinel'"
        ).fetchone() == ("keep",)


def test_repeated_seed_and_normal_startup_preserve_full_business_state(
    client: TestClient, db_path: Path
) -> None:
    first = add(client, quantity=2, key="seed-preserve")
    assert first.status_code == 200
    before = db_state(db_path)
    seed_database(db_path)
    seed_database(db_path)
    assert db_state(db_path) == before
    with TestClient(create_app(db_path)) as second_client:
        assert db_state(db_path) == before
        assert add(second_client, quantity=2, key="seed-preserve").content == first.content
    assert db_state(db_path) == before


def test_seed_and_explicit_reset_commands(client: TestClient, db_path: Path) -> None:
    assert add(client, key="before-reset").status_code == 200
    before = db_state(db_path)
    command = [sys.executable, "-m", "app.backend.seed", "--db", str(db_path)]
    seeded = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=15, check=False)
    assert seeded.returncode == 0 and seeded.stderr == b""
    assert b"without overwrite" in seeded.stdout
    assert db_state(db_path) == before
    reset = subprocess.run(
        [*command, "--reset"], cwd=ROOT, capture_output=True, timeout=15, check=False
    )
    assert reset.returncode == 0 and reset.stderr == b""
    assert b"reset and seeded" in reset.stdout
    cart = client.get("/api/cart").json()
    assert cart["revision"] == 0 and cart["items"] == []
    product = client.get("/api/products/p1").json()
    assert product["inventory_revision"] == 0 and len(product["skus"]) == 7
    with connect(db_path) as connection:
        assert connection.execute("SELECT sum(reserved) FROM skus").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM idempotency_records").fetchone() == (0,)
