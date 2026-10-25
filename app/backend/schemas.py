from pydantic import BaseModel, ConfigDict, Field, field_validator


class AddCartItemRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    sku_id: str = Field(min_length=1, max_length=128)
    quantity: int = Field(ge=1, le=2147483647)

    @field_validator("sku_id")
    @classmethod
    def ascii_sku_id(cls, value: str) -> str:
        if not all("!" <= char <= "~" for char in value):
            raise ValueError("SKU ID must be a printable ASCII token")
        return value


class ProductOption(BaseModel):
    name: str
    values: list[str]


class Sku(BaseModel):
    id: str
    price_minor: int
    available_quantity: int
    image_url: str
    option_values: dict[str, str]


class Product(BaseModel):
    id: str
    name: str
    description: str
    currency: str
    images: list[str]
    options: list[ProductOption]
    inventory_revision: int
    skus: list[Sku]


class CartItem(BaseModel):
    sku_id: str
    quantity: int
    unit_price_minor: int
    line_total_minor: int


class Cart(BaseModel):
    id: str
    revision: int
    currency: str
    items: list[CartItem]
    total_item_count: int
    total_price_minor: int


class InventoryUpdate(BaseModel):
    revision: int
    sku_id: str
    available_quantity: int


class AddCartItemResponse(BaseModel):
    cart: Cart
    inventory: InventoryUpdate


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, object]
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
