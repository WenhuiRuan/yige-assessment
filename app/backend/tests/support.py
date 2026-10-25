import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.backend.db import connect

ROOT = Path(__file__).resolve().parents[3]
TABLES = ("products", "skus", "carts", "cart_items", "idempotency_records", "inventory_meta")


def db_state(path: Path) -> dict[str, list[tuple]]:
    with connect(path) as connection:
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            for table in TABLES
        }


def add(
    client: TestClient | httpx.Client,
    sku: str = "sku-red-s",
    quantity: int = 1,
    key: str | None = None,
) -> httpx.Response:
    return client.post(
        "/api/cart/items",
        json={"sku_id": sku, "quantity": quantity},
        headers={"Idempotency-Key": key if key is not None else str(uuid4())},
    )


def assert_headers(response: httpx.Response) -> None:
    UUID(response.headers["X-Request-ID"])
    assert response.headers["Cache-Control"] == "no-store"


def assert_error(response: httpx.Response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    assert_headers(response)
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["details"], dict)
    UUID(body["error"]["request_id"])
    return body["error"]


@contextmanager
def live_server(application: FastAPI) -> Iterator[str]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            application,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    try:
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Test HTTP server did not start")
            time.sleep(0.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        assert not thread.is_alive(), "Test HTTP server failed to stop"
