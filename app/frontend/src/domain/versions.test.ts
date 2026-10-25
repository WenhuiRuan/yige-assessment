import { expect, test } from 'vitest'
import { added, emptyCart, product, updated } from '../test/fixtures'
import { mergeCart, mergeInventory, mergeProduct } from './versions'

test('FE10 partial v6 followed by full v5 keeps X but updates other older SKUs', () => {
  const initial = mergeProduct(null, product)
  const partial = mergeInventory(initial, { revision: 6, sku_id: 'sku-red-s', available_quantity: 1 })
  expect(partial?.fullRevision).toBe(0)
  const next = mergeProduct(partial, updated(8, 5, 'sku-blue-s'))
  expect(next.fullRevision).toBe(5)
  expect(next.product.skus.find(s => s.id === 'sku-red-s')?.available_quantity).toBe(1)
  expect(next.skuRevisions['sku-red-s']).toBe(6)
  expect(next.product.skus.find(s => s.id === 'sku-blue-s')?.available_quantity).toBe(8)
  expect(next.skuRevisions['sku-blue-s']).toBe(5)
})
test('FE10 newer stock increases, decreases and reaches zero; old replay is ignored', () => {
  let state = mergeProduct(null, updated(8, 4))
  state = mergeProduct(state, updated(2, 5))
  state = mergeProduct(state, updated(0, 6))
  expect(state.product.skus.find(s => s.id === 'sku-red-s')?.available_quantity).toBe(0)
  expect(mergeInventory(state, added(1, 3).inventory)).toBe(state)
  expect(mergeProduct(state, updated(5, 2))).toBe(state)
  state = mergeProduct(state, updated(10, 7))
  expect(state.product.skus.find(s => s.id === 'sku-red-s')?.available_quantity).toBe(10)
})
test('FE10 removed combination stays removed but a newer partial SKU survives older omission', () => {
  const without = { ...updated(5, 5), skus: product.skus.filter(s => s.id !== 'sku-red-s') }
  const removed = mergeProduct(mergeProduct(null, product), without)
  expect(removed.product.skus.some(s => s.id === 'sku-red-s')).toBe(false)
  expect(mergeProduct(removed, product)).toBe(removed)
  const known6 = mergeInventory(mergeProduct(null, product), { revision: 6, sku_id: 'sku-red-s', available_quantity: 2 })
  expect(mergeProduct(known6, without).product.skus.some(s => s.id === 'sku-red-s')).toBe(true)
})
test('FE10 cart revisions are independent and never decrease', () => {
  const cart = added(2, 9).cart
  expect(mergeCart(cart, emptyCart)).toBe(cart)
  expect(mergeCart(cart, added(3, 10).cart).total_item_count).toBe(3)
})
