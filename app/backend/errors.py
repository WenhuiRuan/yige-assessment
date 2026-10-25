"""Public errors deliberately exclude Pydantic input values and internal exceptions."""

import json
import sqlite3

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, details: dict[str, object] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details if details is not None else {}

    def body(self, request_id: str) -> dict[str, object]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "request_id": request_id,
            }
        }


def encode_body(body: dict[str, object]) -> str:
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def validation_error(field: str, message: str) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_ERROR",
        "Invalid request",
        {
            "fields": [{"field": field, "message": message}],
        },
    )


def unexpected_error(error: Exception) -> ApiError:
    code = getattr(error, "sqlite_errorcode", 0) or 0
    if isinstance(error, sqlite3.OperationalError) and (code & 0xFF) in (
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    ):
        return ApiError(503, "TEMPORARILY_UNAVAILABLE", "Please retry later")
    return ApiError(500, "INTERNAL_ERROR", "Unexpected server error")


async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(error.body(request.state.request_id), status_code=error.status)


async def request_validation_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    messages = {
        "missing": "Field is required",
        "int_type": "Must be an integer",
        "string_type": "Must be a string",
        "extra_forbidden": "Unknown fields are not allowed",
        "json_invalid": "Malformed JSON",
        "greater_than_equal": "Value is too small",
        "less_than_equal": "Value is too large",
    }
    fields = []
    for item in error.errors():
        location = item.get("loc", ())
        last = location[-1] if location else "body"
        field = last if last in ("sku_id", "quantity", "Idempotency-Key") else "body"
        fields.append({"field": field, "message": messages.get(item["type"], "Invalid value")})
    public = ApiError(422, "VALIDATION_ERROR", "Invalid request", {"fields": fields})
    return JSONResponse(public.body(request.state.request_id), status_code=422)
