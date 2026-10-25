"""Application factory, uniform request errors/headers, and persistent demo API."""

import logging
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from app.backend.db import REPOSITORY_ROOT, database_path, probe_database
from app.backend.errors import (
    ApiError,
    api_error_handler,
    request_validation_handler,
    unexpected_error,
    validation_error,
)
from app.backend.routes.api import router
from app.backend.seed import seed_database

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    database: str
    stage: str


def create_app(db_path: Path | None = None, *, busy_timeout_seconds: float = 5.0) -> FastAPI:
    path = db_path if db_path is not None else database_path()

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        seed_database(path, timeout=busy_timeout_seconds)
        yield

    application = FastAPI(title="Yige assessment", version="0.1.0", lifespan=lifespan)
    application.state.db_path = path
    application.state.db_timeout = busy_timeout_seconds
    application.add_exception_handler(ApiError, api_error_handler)
    application.add_exception_handler(RequestValidationError, request_validation_handler)

    @application.exception_handler(HTTPException)
    async def parsing_error(request: Request, error: HTTPException) -> Response:
        if error.status_code == 400:
            # FastAPI uses 400 for malformed encodings/overlong JSON integer parsing too.
            return await api_error_handler(request, validation_error("body", "Malformed JSON"))
        return await http_exception_handler(request, error)

    @application.middleware("http")
    async def request_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception as error:
            public = unexpected_error(error)
            # No raw request, exception text, stack, SQL, or internal path in this log.
            logger.error("Request failed: id=%s status=%s", request.state.request_id, public.status)
            response = JSONResponse(
                public.body(request.state.request_id), status_code=public.status
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    application.include_router(router)
    application.mount(
        "/images",
        StaticFiles(directory=REPOSITORY_ROOT / "app/frontend/public/images"),
        name="images",
    )

    @application.get("/api/health", response_model=HealthResponse, tags=["engineering"])
    def health() -> HealthResponse:
        # Synchronous route: SQLite work runs in FastAPI's thread pool.
        try:
            probe_database(path)
        except sqlite3.Error as error:
            raise ApiError(
                503, "TEMPORARILY_UNAVAILABLE", "Database health check failed"
            ) from error
        # Preserve the P0 probe wire format; "stage" is a compatibility marker, not readiness.
        return HealthResponse(status="ok", database="sqlite", stage="P0")

    return application


app = create_app()
