import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.backend.db import connect
from app.backend.services import cart, reads
from app.backend.tests.support import add, assert_headers, live_server


@pytest.mark.parametrize("mode", ["last-unit", "same-key-same-payload", "same-key-conflict"])
def test_api08_09_10_real_http_races(
    application: FastAPI, db_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    barrier = threading.Barrier(2)
    records = []
    traces: list[list[str]] = []
    record_lock = threading.Lock()
    original_connect = cart.connect

    @contextmanager
    def simultaneous_connect(path, timeout=5.0):
        with original_connect(path, timeout) as connection:
            trace = []
            connection.set_trace_callback(trace.append)
            actual_path = connection.execute("PRAGMA database_list").fetchone()[2]
            assert not connection.in_transaction
            with record_lock:
                records.append((id(connection), threading.get_ident(), actual_path))
                traces.append(trace)
            barrier.wait(
                timeout=5
            )  # Both have a connection; neither holds a transaction/write lock.
            yield connection

    monkeypatch.setattr(cart, "connect", simultaneous_connect)
    sku = "sku-red-xl" if mode == "last-unit" else "sku-red-s"
    quantities = [1, 2] if mode == "same-key-conflict" else [1, 1]
    keys = ["race-one", "race-two"] if mode == "last-unit" else ["shared", "shared"]
    with live_server(application) as base_url:

        def post(index: int) -> httpx.Response:
            with httpx.Client(base_url=base_url, timeout=10) as client:
                return add(client, sku, quantities[index], keys[index])

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(post, index) for index in range(2)]
            responses = [future.result(timeout=15) for future in futures]
        statuses = sorted(response.status_code for response in responses)
        assert statuses == ([200, 200] if mode == "same-key-same-payload" else [200, 409])
        for response in responses:
            assert_headers(response)
        assert len({r.headers["X-Request-ID"] for r in responses}) == 2
        if mode == "same-key-same-payload":
            assert responses[0].content == responses[1].content
        else:
            error = next(r for r in responses if r.status_code == 409).json()["error"]
            assert error["code"] == (
                "INSUFFICIENT_STOCK" if mode == "last-unit" else "IDEMPOTENCY_CONFLICT"
            )
        success = next(r for r in responses if r.status_code == 200).json()
        applied = success["cart"]["total_item_count"]
        assert applied in quantities
        with connect(db_path) as connection:
            assert connection.execute("SELECT sum(reserved) FROM skus").fetchone() == (applied,)
            assert connection.execute("SELECT sum(quantity) FROM cart_items").fetchone() == (
                applied,
            )
            assert connection.execute("SELECT revision FROM carts").fetchone() == (1,)
            assert connection.execute("SELECT revision FROM inventory_meta").fetchone() == (1,)
            assert connection.execute("SELECT count(*) FROM idempotency_records").fetchone() == (
                2 if mode == "last-unit" else 1,
            )
    assert len(records) == 2
    assert len({item[0] for item in records}) == len({item[1] for item in records}) == 2
    assert {Path(item[2]).resolve() for item in records} == {db_path.resolve()}
    assert all("BEGIN IMMEDIATE" in trace for trace in traces)
    updates = [
        sql for trace in traces for sql in trace if sql.startswith("UPDATE skus SET reserved")
    ]
    assert len(updates) == (2 if mode == "last-unit" else 1)
    assert all("AND on_hand - reserved >=" in sql for sql in updates)
    print(
        f"\n{mode}: real HTTP statuses={statuses}; same file, 2 connections/threads, "
        f"barrier before BEGIN; reserved/cart delta={applied}, revisions=1"
    )


@pytest.mark.parametrize("domain", ["product", "cart"])
def test_get_snapshot_is_consistent_while_real_writer_waits_to_commit(
    application: FastAPI, monkeypatch: pytest.MonkeyPatch, domain: str
) -> None:
    begin_writer = threading.Event()
    prepared = threading.Event()
    finished = threading.Event()
    first_read = True
    original_store = cart._store_result
    helper = "_read_skus" if domain == "product" else "_read_cart_items"
    original_read = getattr(reads, helper)

    def mark_prepared(*args, **kwargs):
        original_store(*args, **kwargs)
        prepared.set()  # SQL has executed, but COMMIT has not returned.

    def between_read_queries(connection, *args):
        nonlocal first_read
        if first_read:
            first_read = False
            assert connection.in_transaction
            begin_writer.set()
            assert prepared.wait(timeout=3)
            # Rollback-journal readers hold a snapshot until their explicit transaction ends.
            assert not finished.wait(timeout=0.05)
        return original_read(connection, *args)

    monkeypatch.setattr(cart, "_store_result", mark_prepared)
    monkeypatch.setattr(reads, helper, between_read_queries)
    with live_server(application) as base_url:

        def write():
            assert begin_writer.wait(timeout=3)
            with httpx.Client(base_url=base_url, timeout=10) as writer:
                response = add(writer, key="snapshot-writer")
            finished.set()
            return response

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(write)
            with httpx.Client(base_url=base_url, timeout=10) as reader:
                url = "/api/products/p1" if domain == "product" else "/api/cart"
                response = reader.get(url)
                assert response.status_code == 200
                old = response.json()
                if domain == "product":
                    assert old["inventory_revision"] == 0
                    assert (
                        next(s for s in old["skus"] if s["id"] == "sku-red-s")["available_quantity"]
                        == 5
                    )
                else:
                    assert old["revision"] == 0 and old["items"] == []
                assert future.result(timeout=10).status_code == 200
                new = reader.get(url).json()
                assert new["inventory_revision" if domain == "product" else "revision"] == 1
    assert finished.is_set()
    print(f"\n{domain} GET: snapshot revision=0 during uncommitted write; next read revision=1")
