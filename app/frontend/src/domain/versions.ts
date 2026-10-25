import type { AddCartItemResponse, Cart, Product } from '../api/contracts'

export interface InventoryState {
  product: Product
  fullRevision: number
  skuRevisions: Record<string, number>
}

export function mergeProduct(current: InventoryState | null, incoming: Product): InventoryState {
  const revision = incoming.inventory_revision
  if (current && revision < current.fullRevision) return current
  const revisions = { ...current?.skuRevisions }
  const skus = incoming.skus.map(sku => {
    const old = current?.product.skus.find(item => item.id === sku.id)
    if (old && (revisions[sku.id] ?? 0) > revision) return old
    revisions[sku.id] = revision
    return sku
  })
  // A newer single-SKU result survives even a full snapshot that omits that SKU.
  for (const old of current?.product.skus ?? []) {
    if (!incoming.skus.some(sku => sku.id === old.id)) {
      if ((revisions[old.id] ?? 0) > revision) skus.push(old)
      else revisions[old.id] = revision // tombstone: older data cannot resurrect it
    }
  }
  skus.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
  return { product: { ...incoming, skus }, fullRevision: revision, skuRevisions: revisions }
}

export function mergeInventory(current: InventoryState | null, update: AddCartItemResponse['inventory']): InventoryState | null {
  if (!current || update.revision < (current.skuRevisions[update.sku_id] ?? current.fullRevision)) return current
  return {
    ...current, // A partial result MUST NOT advance fullRevision.
    product: { ...current.product, skus: current.product.skus.map(sku => sku.id === update.sku_id
      ? { ...sku, available_quantity: update.available_quantity } : sku) },
    skuRevisions: { ...current.skuRevisions, [update.sku_id]: update.revision },
  }
}

export function mergeCart(current: Cart | null, incoming: Cart): Cart {
  return current && current.revision > incoming.revision ? current : incoming
}
