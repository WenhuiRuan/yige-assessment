import type { AddCartItemResponse, ApiErrorCode, ApiErrorResponse, Cart, Product, Sku } from './contracts'

function fail(): never { throw new Error('Invalid API response') }
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
export function record(value: unknown): Record<string, unknown> { return isRecord(value) ? value : fail() }
function text(value: unknown): string { return typeof value === 'string' && value.length > 0 ? value : fail() }
export function integer(value: unknown, minimum = 0): number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum ? value : fail()
}
function array(value: unknown): unknown[] { return Array.isArray(value) ? value : fail() }
function unique(values: string[]): void { if (new Set(values).size !== values.length) fail() }
function image(value: unknown): string {
  const path = text(value)
  return /^\/images\/[a-z0-9-]+\.(svg|png|webp|jpg)$/.test(path) ? path : fail()
}
function currency(value: unknown): 'CNY' { return value === 'CNY' ? value : fail() }

export function parseProduct(value: unknown): Product {
  const body = record(value)
  const options = array(body.options).map(item => {
    const option = record(item)
    const values = array(option.values).map(text)
    if (!values.length) fail()
    unique(values)
    return { name: text(option.name), values }
  })
  unique(options.map(option => option.name))
  if (options.length < 2) fail()
  const skus: Sku[] = array(body.skus).map(item => {
    const sku = record(item)
    const raw = record(sku.option_values)
    const option_values: Record<string, string> = {}
    if (Object.keys(raw).length !== options.length) fail()
    for (const option of options) {
      const v = text(raw[option.name])
      if (!option.values.includes(v)) fail()
      option_values[option.name] = v
    }
    return { id: text(sku.id), price_minor: integer(sku.price_minor),
      available_quantity: integer(sku.available_quantity), image_url: image(sku.image_url), option_values }
  })
  // Refreshes may remove a SKU; require valid data rather than freezing the original seed count.
  if (!skus.length) fail()
  unique(skus.map(sku => sku.id))
  unique(skus.map(sku => JSON.stringify(options.map(option => sku.option_values[option.name]))))
  const images = array(body.images).map(image)
  if (!images.length) fail()
  return { id: text(body.id), name: text(body.name), description: text(body.description),
    currency: currency(body.currency), images, options, inventory_revision: integer(body.inventory_revision), skus }
}

export function parseCart(value: unknown): Cart {
  const body = record(value)
  const items = array(body.items).map(item => {
    const row = record(item)
    const quantity = integer(row.quantity, 1)
    const unit_price_minor = integer(row.unit_price_minor)
    const line_total_minor = integer(row.line_total_minor)
    if (quantity * unit_price_minor !== line_total_minor) fail()
    return { sku_id: text(row.sku_id), quantity, unit_price_minor, line_total_minor }
  })
  unique(items.map(item => item.sku_id))
  const total_item_count = integer(body.total_item_count)
  const total_price_minor = integer(body.total_price_minor)
  if (items.reduce((sum, row) => sum + row.quantity, 0) !== total_item_count ||
      items.reduce((sum, row) => sum + row.line_total_minor, 0) !== total_price_minor) fail()
  return { id: text(body.id), currency: currency(body.currency), revision: integer(body.revision),
    items, total_item_count, total_price_minor }
}

export function parseAddResult(value: unknown): AddCartItemResponse {
  const body = record(value)
  const inventory = record(body.inventory)
  return { cart: parseCart(body.cart), inventory: { sku_id: text(inventory.sku_id),
    available_quantity: integer(inventory.available_quantity), revision: integer(inventory.revision) } }
}

function errorCode(value: unknown): ApiErrorCode {
  switch (value) {
    case 'VALIDATION_ERROR': case 'PRODUCT_NOT_FOUND': case 'SKU_NOT_FOUND':
    case 'INSUFFICIENT_STOCK': case 'IDEMPOTENCY_CONFLICT': case 'INTERNAL_ERROR':
    case 'TEMPORARILY_UNAVAILABLE': return value
    default: return fail()
  }
}

export function parseError(value: unknown, status: number): ApiErrorResponse {
  const error = record(record(value).error)
  const code = errorCode(error.code)
  const expected = { VALIDATION_ERROR: 422, PRODUCT_NOT_FOUND: 404, SKU_NOT_FOUND: 404,
    INSUFFICIENT_STOCK: 409, IDEMPOTENCY_CONFLICT: 409, INTERNAL_ERROR: 500, TEMPORARILY_UNAVAILABLE: 503 }
  if (status !== expected[code]) fail()
  const details = record(error.details)
  if (code === 'INSUFFICIENT_STOCK') {
    text(details.sku_id); integer(details.requested_quantity, 1)
    integer(details.available_quantity); integer(details.inventory_revision)
  }
  return { error: { code, message: text(error.message), details, request_id: text(error.request_id) } }
}
