import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, test, vi } from 'vitest'
import { App } from './App'
import { added, errorBody, product, updated } from './test/fixtures'
import { server } from './test/server'

function gate() {
  let release = () => {}
  const promise = new Promise<void>(resolve => { release = resolve })
  return { promise, release }
}
async function ready() {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('heading', { name: product.name })
  await waitFor(() => expect(screen.getByTestId('cart-count')).toHaveTextContent('0'))
  return user
}
async function select(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: '红色' }))
  await user.click(screen.getByRole('button', { name: 'S' }))
}
const submitForm = () => fireEvent.submit(screen.getByRole('form', { name: '商品规格与加购' }))

test('FE06 loading, product failure, and local retry without losing the page', async () => {
  server.use(http.get('/api/products/p1', () => new HttpResponse(null, { status: 503 })))
  const user = userEvent.setup(); render(<App />)
  expect(screen.getByText('正在加载商品…')).toBeInTheDocument()
  expect(await screen.findByText('商品加载失败，请重试。')).toHaveAttribute('role', 'alert')
  server.resetHandlers()
  await user.click(screen.getByRole('button', { name: '重试读取商品' }))
  expect(await screen.findByRole('heading', { name: product.name })).toBeInTheDocument()
})
test('FE06 invalid product JSON cannot display a false success', async () => {
  server.use(http.get('/api/products/p1', () => HttpResponse.json({ id: 'p1' })))
  render(<App />)
  expect(await screen.findByText('商品加载失败，请重试。')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: product.name })).not.toBeInTheDocument()
})
test('cart failure displays unknown, not zero; cart can be retried independently', async () => {
  server.use(http.get('/api/cart', () => HttpResponse.error()))
  const user = userEvent.setup(); render(<App />)
  await screen.findByText('购物车读取失败，件数未知。')
  expect(screen.getByTestId('cart-count')).toHaveTextContent('未知')
  await select(user)
  server.use(http.get('/api/cart', () => HttpResponse.json(added(3, 5).cart)))
  await user.click(screen.getByRole('button', { name: '刷新购物车' }))
  await waitFor(() => expect(screen.getByTestId('cart-count')).toHaveTextContent('3'))
  expect(screen.getByRole('button', { name: 'S' })).toHaveAttribute('aria-pressed', 'true')
})
test('FE02/03/04 one SKU drives image, price and stock; candidate disable, clamp, clear', async () => {
  const user = await ready()
  expect(screen.getByRole('img')).toHaveAttribute('src', '/images/product.svg')
  expect(screen.getByRole('button', { name: /加入购物车/ })).toBeDisabled()
  await select(user)
  expect(screen.getByLabelText('价格')).toHaveTextContent('99.00')
  expect(screen.getByRole('img')).toHaveAttribute('src', '/images/sku-red-s.svg')
  expect(screen.getByText('可用库存 5 件')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'L · 售罄' })).toBeDisabled()
  await user.clear(screen.getByLabelText('数量')); await user.type(screen.getByLabelText('数量'), '4')
  await user.click(screen.getByRole('button', { name: 'M' }))
  expect(screen.getByLabelText('数量')).toHaveValue('3')
  expect(screen.getByLabelText('价格')).toHaveTextContent('109.00')
  expect(screen.getByRole('img')).toHaveAttribute('src', '/images/sku-red-m.svg')
  expect(screen.getByText('可用库存 3 件')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '蓝色' }))
  expect(screen.getByLabelText('数量')).toHaveValue('2')
  expect(screen.getByRole('img')).toHaveAttribute('src', '/images/sku-blue-m.svg')
  expect(screen.getByText('可用库存 2 件')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'XL · 不提供' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'L' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: '清空选择' }))
  expect(screen.getByRole('img')).toHaveAttribute('src', '/images/product.svg')
  expect(screen.getByLabelText('数量')).toBeDisabled()
  expect(screen.getByText(/请选择颜色和尺寸/)).toBeInTheDocument()
})
test.each(['', '0', '-1', '1.2', '6', 'x'])('FE04 invalid draft %s never sends POST', async draft => {
  let posts = 0
  server.use(http.post('/api/cart/items', () => { posts++; return HttpResponse.json(added()) }))
  const user = await ready(); await select(user)
  fireEvent.change(screen.getByLabelText('数量'), { target: { value: draft } })
  submitForm()
  expect(screen.getByRole('button', { name: /加入购物车/ })).toBeDisabled()
  expect(screen.getByRole('alert')).toHaveTextContent('数量无效')
  expect(posts).toBe(0)
})
test('FE05 same-frame submit, double click and keyboard repeat use the synchronous lock', async () => {
  const held = gate(); let posts = 0
  server.use(http.post('/api/cart/items', async () => { posts++; await held.promise; return HttpResponse.json(added()) }))
  const user = await ready(); await select(user)
  const button = screen.getByRole('button', { name: /加入购物车/ })
  act(() => { submitForm(); submitForm(); submitForm() })
  await user.dblClick(button)
  await user.keyboard('{Enter}{Enter}')
  await waitFor(() => expect(posts).toBe(1))
  expect(screen.getByLabelText('数量')).toBeDisabled()
  expect(screen.getByRole('button', { name: '红色' })).toBeDisabled()
  held.release()
  expect(await screen.findByText('本次已成功加入 1 件商品。')).toHaveAttribute('role', 'status')
})
test.each(['network', '500', '503', 'malformed'])('FE07/09 %s result retains key/payload until confirmed; then new intent gets new key', async failure => {
  const calls: { key: string | null; body: unknown }[] = []
  server.use(http.post('/api/cart/items', async ({ request }) => {
    calls.push({ key: request.headers.get('Idempotency-Key'), body: await request.json() })
    if (calls.length === 1) {
      if (failure === 'network') return HttpResponse.error()
      if (failure === 'malformed') return HttpResponse.json({})
      return HttpResponse.json(errorBody(failure === '500' ? 'INTERNAL_ERROR' : 'TEMPORARILY_UNAVAILABLE'), { status: Number(failure) })
    }
    return HttpResponse.json(added())
  }))
  const user = await ready(); await select(user)
  await user.click(screen.getByRole('button', { name: /加入购物车/ }))
  const retry = await screen.findByRole('button', { name: '重试确认本次加购' })
  expect(screen.getByRole('button', { name: /等待本次/ })).toBeDisabled()
  expect(screen.getByLabelText('数量')).toBeDisabled()
  // A GET count change cannot identify the pending operation.
  server.use(http.get('/api/cart', () => HttpResponse.json(added(2, 4).cart)))
  await user.click(screen.getByRole('button', { name: '刷新购物车' }))
  await waitFor(() => expect(screen.getByTestId('cart-count')).toHaveTextContent('2'))
  expect(retry).toBeInTheDocument()
  await user.click(retry)
  await screen.findByText('本次已成功加入 1 件商品。')
  expect(calls[1]).toEqual(calls[0])
  expect(calls[0]?.key).toMatch(/^[0-9a-f-]{36}$/)
  expect(screen.getByTestId('cart-count')).toHaveTextContent('2') // older replay cart v1 ignored
  await user.click(screen.getByRole('button', { name: /加入购物车/ }))
  await waitFor(() => expect(calls).toHaveLength(3))
  expect(calls[2]?.key).not.toBe(calls[0]?.key)
})
test('FE08 stock rejection updates and clamps; later zero/increase and removed SKU remain correct', async () => {
  let posts = 0
  server.use(http.post('/api/cart/items', () => {
    posts++
    return HttpResponse.json(errorBody('INSUFFICIENT_STOCK', { sku_id: 'sku-red-s', requested_quantity: 4,
      available_quantity: 2, inventory_revision: 4 }), { status: 409 })
  }))
  const user = await ready(); await select(user)
  fireEvent.change(screen.getByLabelText('数量'), { target: { value: '4' } })
  await user.click(screen.getByRole('button', { name: /加入购物车/ }))
  await screen.findByText(/库存不足，本次未加入/)
  expect(screen.getByText('可用库存 2 件')).toBeInTheDocument()
  expect(screen.getByLabelText('数量')).toHaveValue('2')
  server.use(http.get('/api/products/p1', () => HttpResponse.json(updated(0, 5))))
  await user.click(screen.getByRole('button', { name: '刷新商品库存' }))
  await screen.findByText(/此规格已售罄/)
  expect(screen.getByLabelText('数量')).toBeDisabled()
  expect(screen.getByLabelText('数量')).not.toHaveAttribute('max', '0')
  server.use(http.get('/api/products/p1', () => HttpResponse.json(updated(8, 6))))
  await user.click(screen.getByRole('button', { name: '刷新商品库存' }))
  await screen.findByText('可用库存 8 件')
  server.use(http.get('/api/products/p1', () => HttpResponse.json({ ...updated(8, 7), skus: product.skus.filter(s => s.id !== 'sku-red-s') })))
  await user.click(screen.getByRole('button', { name: '刷新商品库存' }))
  await screen.findByText(/此组合不提供/)
  expect(screen.getByRole('img')).toHaveAttribute('src', '/images/product.svg')
  expect(posts).toBe(1)
  await user.click(screen.getByRole('button', { name: '清空选择' }))
  await screen.findByText(/请选择颜色和尺寸/)
})
test('FE09 validation needs an edited payload; conflict never automatically changes key', async () => {
  const calls: (string | null)[] = []
  server.use(http.post('/api/cart/items', ({ request }) => {
    calls.push(request.headers.get('Idempotency-Key'))
    return HttpResponse.json(errorBody(calls.length === 1 ? 'VALIDATION_ERROR' : 'IDEMPOTENCY_CONFLICT'), { status: calls.length === 1 ? 422 : 409 })
  }))
  const user = await ready(); await select(user)
  await user.click(screen.getByRole('button', { name: /加入购物车/ }))
  await screen.findByText(/服务器拒绝了本次输入/)
  expect(screen.getByRole('button', { name: /加入购物车/ })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('数量'), { target: { value: '2' } })
  await user.click(screen.getByRole('button', { name: /加入购物车/ }))
  await screen.findByText(/本次操作标识发生冲突/)
  submitForm()
  expect(calls).toHaveLength(2)
  expect(calls[0]).not.toBe(calls[1])
  expect(screen.queryByRole('button', { name: '重试确认本次加购' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('数量')).toBeDisabled()
})
test('FE11 successful POST survives both GET failures; retries only read', async () => {
  let posts = 0
  server.use(http.post('/api/cart/items', () => {
    posts++
    server.use(http.get('/api/products/p1', () => HttpResponse.error()), http.get('/api/cart', () => HttpResponse.error()))
    return HttpResponse.json(added(1, 2))
  }))
  const user = await ready(); await select(user)
  await user.click(screen.getByRole('button', { name: /加入购物车/ }))
  await screen.findByText('本次已成功加入 1 件商品。')
  await screen.findByText('最新库存同步失败，保留上次已知数据。')
  await screen.findByText('购物车读取失败，显示上次确认件数。')
  expect(screen.getByTestId('cart-count')).toHaveTextContent('1')
  server.use(http.get('/api/products/p1', () => HttpResponse.json(updated(4, 2))), http.get('/api/cart', () => HttpResponse.json(added(1, 2).cart)))
  await user.click(screen.getByRole('button', { name: '重试读取商品' }))
  await user.click(screen.getByRole('button', { name: '刷新购物车' }))
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  expect(screen.getByText('本次已成功加入 1 件商品。')).toBeInTheDocument()
  expect(posts).toBe(1)
})
test('FE10 obsolete GET is cancelled even if its later body advertises a higher revision', async () => {
  const held = gate(); let reads = 0
  server.use(http.get('/api/products/p1', async () => {
    if (++reads === 1) { await held.promise; return HttpResponse.json(updated(99, 99)) }
    return HttpResponse.json(updated(2, 5))
  }))
  const user = userEvent.setup(); render(<App />)
  await waitFor(() => expect(reads).toBe(1))
  await user.click(screen.getByRole('button', { name: '刷新商品库存' }))
  await screen.findByRole('heading', { name: product.name }); await select(user)
  expect(screen.getByText('可用库存 2 件')).toBeInTheDocument()
  await act(async () => { held.release(); await held.promise })
  expect(screen.queryByText('可用库存 99 件')).not.toBeInTheDocument()
})
test('FE10 stale idempotent POST inventory never rolls back a newer GET', async () => {
  let posts = 0
  server.use(http.post('/api/cart/items', () => ++posts === 1 ? HttpResponse.error() : HttpResponse.json(added(1, 1, 4))))
  const user = await ready(); await select(user)
  await user.click(screen.getByRole('button', { name: /加入购物车/ }))
  await screen.findByRole('button', { name: '重试确认本次加购' })
  server.use(http.get('/api/products/p1', () => HttpResponse.json(updated(9, 6))))
  await user.click(screen.getByRole('button', { name: '刷新商品库存' }))
  await screen.findByText('可用库存 9 件')
  await user.click(screen.getByRole('button', { name: '重试确认本次加购' }))
  await screen.findByText('本次已成功加入 1 件商品。')
  expect(screen.getByText('可用库存 9 件')).toBeInTheDocument()
})
test('FE07 real timeout cancels waiting and preserves the exact operation for retry', async () => {
  const held = gate(); const calls: { key: string | null; body: unknown }[] = []
  server.use(http.post('/api/cart/items', async ({ request }) => {
    calls.push({ key: request.headers.get('Idempotency-Key'), body: await request.json() })
    if (calls.length === 1) await held.promise
    return HttpResponse.json(added())
  }))
  const user = await ready(); await select(user)
  vi.useFakeTimers()
  try {
    submitForm()
    await act(async () => { await vi.advanceTimersByTimeAsync(8001) })
  } finally { vi.useRealTimers() }
  await screen.findByRole('button', { name: '重试确认本次加购' })
  held.release()
  await user.click(screen.getByRole('button', { name: '重试确认本次加购' }))
  await screen.findByText('本次已成功加入 1 件商品。')
  expect(calls).toHaveLength(2); expect(calls[1]).toEqual(calls[0])
})
