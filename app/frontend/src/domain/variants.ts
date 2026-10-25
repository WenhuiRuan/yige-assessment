import type { Product, Sku } from '../api/contracts'

export type Selection = Record<string, string>
export type Variant =
  | { kind: 'incomplete' | 'invalid' }
  | { kind: 'out_of_stock' | 'available'; sku: Sku }

export function resolveVariant(product: Product, selection: Selection): Variant {
  if (product.options.some(option => !selection[option.name])) return { kind: 'incomplete' }
  const sku = product.skus.find(item => product.options.every(
    option => item.option_values[option.name] === selection[option.name],
  ))
  return !sku ? { kind: 'invalid' }
    : { kind: sku.available_quantity > 0 ? 'available' : 'out_of_stock', sku }
}

export function optionAvailability(product: Product, selection: Selection, dimension: string, value: string) {
  const compatible = product.skus.filter(sku => sku.option_values[dimension] === value &&
    product.options.every(option => option.name === dimension || !selection[option.name] ||
      sku.option_values[option.name] === selection[option.name]))
  return compatible.length === 0 ? 'unavailable'
    : compatible.some(sku => sku.available_quantity > 0) ? 'available' : 'out_of_stock'
}

export function parseQuantity(draft: string, maximum: number): number | null {
  if (!/^[1-9][0-9]*$/.test(draft)) return null
  const value = Number(draft)
  return Number.isSafeInteger(value) && value <= maximum && value <= 2147483647 ? value : null
}

export function clampQuantity(draft: string, maximum: number): string {
  const value = /^[1-9][0-9]*$/.test(draft) ? Number(draft) : 1
  return String(Math.max(1, Math.min(Number.isSafeInteger(value) ? value : 1, maximum)))
}
