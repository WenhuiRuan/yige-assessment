import { expect, test } from 'vitest'
import { added, emptyCart, errorBody, product } from '../test/fixtures'
import { parseAddResult, parseCart, parseError, parseProduct } from './validation'

test('real backend-shaped Product, Cart and POST responses are checked and reconstructed', () => {
  expect(parseProduct(product)).toEqual(product)
  expect(parseCart(emptyCart)).toEqual(emptyCart)
  expect(parseAddResult(added())).toEqual(added())
})
test.each([null, [], {}, { ...product, currency: 'USD' }, { ...product, inventory_revision: 0.5 },
  { ...product, skus: [{ ...product.skus[0], available_quantity: true }] },
  { ...product, images: ['https://example.com/untrusted.svg'] },
  { ...product, options: [...product.options, product.options[0]] }])('rejects malformed unknown product JSON %#', value => {
  expect(() => parseProduct(value)).toThrow()
})
test.each([true, '1', 1.5, -1, 9007199254740992])('rejects non-safe cart revision %s', revision => {
  expect(() => parseCart({ ...emptyCart, revision })).toThrow()
})
test('rejects inconsistent totals, duplicates, zero cart quantity and incomplete POST body', () => {
  expect(() => parseCart({ ...added().cart, total_price_minor: 1 })).toThrow()
  expect(() => parseCart({ ...added().cart, items: [...added().cart.items, ...added().cart.items] })).toThrow()
  expect(() => parseCart({ ...added().cart, items: [{ ...added().cart.items[0], quantity: 0 }] })).toThrow()
  expect(() => parseAddResult({ cart: emptyCart })).toThrow()
})
test('structured failures require known status/code and complete stock details', () => {
  expect(parseError(errorBody('VALIDATION_ERROR'), 422).error.code).toBe('VALIDATION_ERROR')
  expect(() => parseError(errorBody('INTERNAL_ERROR'), 200)).toThrow()
  expect(() => parseError(errorBody('INSUFFICIENT_STOCK'), 409)).toThrow()
  expect(() => parseError({ detail: 'private' }, 500)).toThrow()
})
