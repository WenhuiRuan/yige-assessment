"""Independent SQLite connections and explicit transaction boundaries."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def database_path() -> Path:
    path = Path(os.environ.get("YIGE_DB_PATH", "data/yige.sqlite3")).expanduser()
    return path if path.is_absolute() else REPOSITORY_ROOT / path


@contextmanager
def connect(path: Path, timeout: float = 5.0) -> Iterator[sqlite3.Connection]:
    # Each caller owns its connection; no global connection or process-local inventory lock.
    connection = sqlite3.connect(path, timeout=timeout, isolation_level=None)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


@contextmanager
def transaction(
    connection: sqlite3.Connection, mode: Literal["DEFERRED", "IMMEDIATE"] = "DEFERRED"
) -> Iterator[None]:
    connection.execute(f"BEGIN {mode}")
    try:
        yield
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def initialize_database(path: Path, timeout: float = 5.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path, timeout) as connection:
        # The static schema script owns its BEGIN/COMMIT; never nest executescript in a transaction.
        connection.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))


def probe_database(path: Path) -> None:
    with connect(path) as connection:
        row = connection.execute(
            "SELECT value FROM app_meta WHERE name = 'schema_stage'"
        ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError("Database bootstrap metadata is missing")
