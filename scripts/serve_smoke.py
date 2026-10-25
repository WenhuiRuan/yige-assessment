"""Start the smoke-test API with an isolated temporary SQLite file."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn


def main() -> None:
    with TemporaryDirectory(prefix="yige-smoke-") as directory:
        os.environ["YIGE_DB_PATH"] = str(Path(directory) / "smoke.sqlite3")
        uvicorn.run("app.backend.main:app", host="127.0.0.1", port=18000)


if __name__ == "__main__":
    main()
