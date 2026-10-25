from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response

from app.backend.errors import validation_error
from app.backend.schemas import (
    AddCartItemRequest,
    AddCartItemResponse,
    Cart,
    ErrorResponse,
    Product,
)
from app.backend.services import cart, reads

router = APIRouter(prefix="/api")
ERROR_RESPONSES = {code: {"model": ErrorResponse} for code in (404, 409, 422, 500, 503)}


def required_key(request: Request, value: Annotated[str, Header(alias="Idempotency-Key")]) -> str:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise validation_error("body", "Content-Type must be application/json")
    if len(request.headers.getlist("idempotency-key")) != 1 or not (
        1 <= len(value) <= 128 and all("!" <= char <= "~" for char in value)
    ):
        raise validation_error(
            "Idempotency-Key", "Must be one printable ASCII token of 1-128 characters"
        )
    return value


@router.get("/products/{product_id}", response_model=Product, responses=ERROR_RESPONSES)
def product(product_id: str, request: Request) -> Product:
    return reads.get_product(request.app.state.db_path, product_id, request.app.state.db_timeout)


@router.get("/cart", response_model=Cart, responses=ERROR_RESPONSES)
def get_cart(request: Request) -> Cart:
    return reads.get_cart(request.app.state.db_path, request.app.state.db_timeout)


@router.post("/cart/items", response_model=AddCartItemResponse, responses=ERROR_RESPONSES)
def add_cart_item(
    payload: AddCartItemRequest, request: Request, key: Annotated[str, Depends(required_key)]
) -> Response:
    result = cart.add_item(
        request.app.state.db_path,
        payload,
        key,
        request.state.request_id,
        request.app.state.db_timeout,
    )
    return Response(result.body, status_code=result.status, media_type="application/json")
