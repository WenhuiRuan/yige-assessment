import type { Product, Cart, AddCartItemResponse } from '../api/contracts'

export const product: Product = {
  "id": "p1",
  "name": "Variant Demo Tee",
  "description": "用于规格选择和库存预留演示的 T 恤",
  "currency": "CNY",
  "images": [
    "/images/product.svg"
  ],
  "options": [
    {
      "name": "color",
      "values": [
        "red",
        "blue"
      ]
    },
    {
      "name": "size",
      "values": [
        "S",
        "M",
        "L",
        "XL"
      ]
    }
  ],
  "inventory_revision": 0,
  "skus": [
    {
      "id": "sku-blue-l",
      "price_minor": 11900,
      "available_quantity": 6,
      "image_url": "/images/sku-blue-l.svg",
      "option_values": {
        "color": "blue",
        "size": "L"
      }
    },
    {
      "id": "sku-blue-m",
      "price_minor": 10900,
      "available_quantity": 2,
      "image_url": "/images/sku-blue-m.svg",
      "option_values": {
        "color": "blue",
        "size": "M"
      }
    },
    {
      "id": "sku-blue-s",
      "price_minor": 9900,
      "available_quantity": 4,
      "image_url": "/images/sku-blue-s.svg",
      "option_values": {
        "color": "blue",
        "size": "S"
      }
    },
    {
      "id": "sku-red-l",
      "price_minor": 11900,
      "available_quantity": 0,
      "image_url": "/images/sku-red-l.svg",
      "option_values": {
        "color": "red",
        "size": "L"
      }
    },
    {
      "id": "sku-red-m",
      "price_minor": 10900,
      "available_quantity": 3,
      "image_url": "/images/sku-red-m.svg",
      "option_values": {
        "color": "red",
        "size": "M"
      }
    },
    {
      "id": "sku-red-s",
      "price_minor": 9900,
      "available_quantity": 5,
      "image_url": "/images/sku-red-s.svg",
      "option_values": {
        "color": "red",
        "size": "S"
      }
    },
    {
      "id": "sku-red-xl",
      "price_minor": 12900,
      "available_quantity": 1,
      "image_url": "/images/sku-red-xl.svg",
      "option_values": {
        "color": "red",
        "size": "XL"
      }
    }
  ]
}
export const emptyCart: Cart = {"id": "demo", "revision": 0, "currency": "CNY", "items": [], "total_item_count": 0, "total_price_minor": 0}

export function added(quantity = 1, revision = 1, available = 5 - quantity): AddCartItemResponse {
  return { cart: { ...emptyCart, revision, items: [{ sku_id: 'sku-red-s', quantity,
    unit_price_minor: 9900, line_total_minor: quantity * 9900 }], total_item_count: quantity,
    total_price_minor: quantity * 9900 }, inventory: { revision, sku_id: 'sku-red-s', available_quantity: available } }
}
export function updated(stock: number, revision: number, skuId = 'sku-red-s'): Product {
  return { ...product, inventory_revision: revision, skus: product.skus.map(sku => sku.id === skuId
    ? { ...sku, available_quantity: stock } : { ...sku }) }
}
export function errorBody(code: string, details: Record<string, unknown> = {}) {
  return { error: { code, details, message: 'Test API failure', request_id: 'test-request' } }
}
