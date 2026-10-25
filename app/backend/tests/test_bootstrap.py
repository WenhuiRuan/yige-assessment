from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.db import connect, initialize_database
from app.backend.main import create_app


def test_health_uses_real_sqlite_and_startup_preserves_data(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "smoke.sqlite3"
    with TestClient(create_app(path)) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "sqlite", "stage": "P0"}
        with connect(path) as connection:
            connection.execute("INSERT INTO app_meta VALUES ('sentinel', 'persisted')")
            assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)

    with TestClient(create_app(path)) as client:
        assert client.get("/api/health").status_code == 200
        with connect(path) as connection:
            assert connection.execute(
                "SELECT value FROM app_meta WHERE name = 'sentinel'"
            ).fetchone() == ("persisted",)


def test_database_failure_is_reported_without_internal_details(tmp_path: Path) -> None:
    path = tmp_path / "smoke.sqlite3"
    with TestClient(create_app(path)) as client:
        with connect(path) as connection:
            connection.execute("DROP TABLE app_meta")
        response = client.get("/api/health")
        assert response.status_code == 503
        error = response.json()["error"]
        assert error["code"] == "TEMPORARILY_UNAVAILABLE"
        assert error["request_id"]
        assert "app_meta" not in response.text
        assert str(path) not in response.text


def test_bootstrap_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "smoke.sqlite3"
    initialize_database(path)
    initialize_database(path)
    with connect(path) as connection:
        assert connection.execute("SELECT * FROM app_meta").fetchall() == [("schema_stage", "P0")]
