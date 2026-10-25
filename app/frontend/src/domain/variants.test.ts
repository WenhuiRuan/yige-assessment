import { expect, test } from 'vitest'
import { product } from '../test/fixtures'
import { clampQuantity, optionAvailability, parseQuantity, resolveVariant } from './variants'

test('FE01 resolves all four states and the exact SKU', () => {
  expect(resolveVariant(product, {})).toEqual({ kind: 'incomplete' })
  expect(resolveVariant(product, { color: 'red' })).toEqual({ kind: 'incomplete' })
  expect(resolveVariant(product, { color: 'blue', size: 'XL' })).toEqual({ kind: 'invalid' })
  expect(resolveVariant(product, { color: 'red', size: 'L' })).toMatchObject({ kind: 'out_of_stock', sku: { id: 'sku-red-l' } })
  expect(resolveVariant(product, { color: 'red', size: 'S' })).toMatchObject({ kind: 'available', sku: { id: 'sku-red-s' } })
})
test('FE03 candidates use only the other selected dimensions', () => {
  expect(optionAvailability(product, { color: 'blue' }, 'size', 'XL')).toBe('unavailable')
  expect(optionAvailability(product, { color: 'red' }, 'size', 'L')).toBe('out_of_stock')
  expect(optionAvailability(product, {}, 'size', 'L')).toBe('available')
  expect(optionAvailability(product, { color: 'red', size: 'S' }, 'color', 'blue')).toBe('available')
})
test.each(['', '0', '-1', '1.0', '1e0', 'true', ' 1', '01', 'NaN', '6', '9007199254740993'])('FE04 rejects quantity draft %s', value => {
  expect(parseQuantity(value, 5)).toBeNull()
})
test('FE04 integer bounds and clamping', () => {
  expect(parseQuantity('1', 5)).toBe(1); expect(parseQuantity('5', 5)).toBe(5)
  expect(parseQuantity('1', 0)).toBeNull()
  expect(clampQuantity('4', 2)).toBe('2'); expect(clampQuantity('', 2)).toBe('1')
})
