import type { AddCartItemRequest, ApiErrorResponse } from './contracts'
import { parseAddResult, parseCart, parseError, parseProduct } from './validation'

export class ApiFailure extends Error {
  constructor(public kind: 'transport' | 'protocol' | 'http', public status = 0, public response?: ApiErrorResponse) {
    super('API request failed')
  }
}

export async function request<T>(url: string, parse: (value: unknown) => T,
  options: RequestInit = {}, timeoutMs = 8000): Promise<T> {
  const controller = new AbortController()
  const cancel = () => controller.abort()
  options.signal?.addEventListener('abort', cancel, { once: true })
  if (options.signal?.aborted) cancel()
  const timer = window.setTimeout(cancel, timeoutMs)
  try {
    const response = await fetch(url, { ...options, signal: controller.signal, cache: 'no-store' })
    let body: unknown
    try { body = await response.json() } catch { throw new ApiFailure('protocol', response.status) }
    if (!response.ok) {
      let error: ApiErrorResponse
      try { error = parseError(body, response.status) } catch { throw new ApiFailure('protocol', response.status) }
      throw new ApiFailure('http', response.status, error)
    }
    try { return parse(body) } catch { throw new ApiFailure('protocol', response.status) }
  } catch (error) {
    throw error instanceof ApiFailure ? error : new ApiFailure('transport')
  } finally {
    window.clearTimeout(timer)
    options.signal?.removeEventListener('abort', cancel)
  }
}

export const getProduct = (signal: AbortSignal) => request('/api/products/p1', parseProduct, { signal })
export const getCart = (signal: AbortSignal) => request('/api/cart', parseCart, { signal })
export const addCartItem = (payload: AddCartItemRequest, key: string) => request('/api/cart/items', parseAddResult, {
  method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key }, body: JSON.stringify(payload),
})
