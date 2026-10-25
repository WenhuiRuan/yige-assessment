import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { emptyCart, product } from './fixtures'

// Imported only by Vitest setup/tests; never by the normal application.
export const server = setupServer(
  http.get('/api/products/p1', () => HttpResponse.json(product)),
  http.get('/api/cart', () => HttpResponse.json(emptyCart)),
)
