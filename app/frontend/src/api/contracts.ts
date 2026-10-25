// Real backend wire contract. JSON is validated at runtime in validation.ts.
// API examples and error semantics are documented in the root README.md.
export interface ProductOption {
  name: string
  values: string[]
}

export interface Sku {
  id: string
  price_minor: number
  available_quantity: number
  image_url: string
  option_values: Record<string, string>
}

export interface Product {
  id: string
  name: string
  description: string
  currency: string
  images: string[]
  options: ProductOption[]
  inventory_revision: number
  skus: Sku[]
}

export interface CartItem {
  sku_id: string
  quantity: number
  unit_price_minor: number
  line_total_minor: number
}

export interface Cart {
  id: string
  revision: number
  currency: string
  items: CartItem[]
  total_item_count: number
  total_price_minor: number
}

export interface AddCartItemRequest {
  sku_id: string
  quantity: number
}

export interface AddCartItemResponse {
  cart: Cart
  inventory: { revision: number; sku_id: string; available_quantity: number }
}

export type ApiErrorCode =
  | 'VALIDATION_ERROR'
  | 'PRODUCT_NOT_FOUND'
  | 'SKU_NOT_FOUND'
  | 'INSUFFICIENT_STOCK'
  | 'IDEMPOTENCY_CONFLICT'
  | 'INTERNAL_ERROR'
  | 'TEMPORARILY_UNAVAILABLE'

export interface ApiErrorResponse {
  error: {
    code: ApiErrorCode
    message: string
    details: Record<string, unknown>
    request_id: string
  }
}
