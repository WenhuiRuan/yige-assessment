import { expect, test } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { parseAddResult, parseCart, parseProduct } from '../src/api/validation'

// All application/API requests use real FastAPI + one isolated temporary SQLite file.
for (const width of [375, 1280]) {
  test(`E2E01 real selection/add and usable ${width}px layout`, async ({ page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const initial = parseCart(await (await request.get('/api/cart')).json())
    const initialProduct = parseProduct(await (await request.get('/api/products/p1')).json())
    const before = initialProduct.skus.find(s => s.id === 'sku-blue-l')?.available_quantity
    expect(before).toBeGreaterThan(0)
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Variant Demo Tee' })).toBeVisible()
    await expect(page.getByRole('button', { name: /加入购物车/ })).toBeDisabled()
    await expect(page.getByRole('img')).toHaveAttribute('src', '/images/product.svg')
    await page.getByRole('button', { name: '蓝色', exact: true }).click()
    await expect(page.getByRole('button', { name: 'XL · 不提供', exact: true })).toBeDisabled()
    await page.getByRole('button', { name: 'L', exact: true }).click()
    await expect(page.getByLabel('价格')).toHaveText('¥119.00')
    await expect(page.getByRole('img')).toHaveAttribute('src', '/images/sku-blue-l.svg')
    await expect(page.getByRole('img')).toHaveJSProperty('naturalWidth', 640)
    await expect(page.getByText(`可用库存 ${before} 件`)).toBeVisible()
    const post = page.waitForResponse(response => response.url().endsWith('/api/cart/items') && response.request().method() === 'POST')
    await page.getByRole('button', { name: /加入购物车/ }).click()
    const response = await post
    expect(response.status()).toBe(200)
    const result = parseAddResult(await response.json())
    expect(result.cart.total_item_count).toBe(initial.total_item_count + 1)
    expect(result.inventory.available_quantity).toBe((before ?? 0) - 1)
    await expect(page.getByText('本次已成功加入 1 件商品。')).toBeVisible()
    await expect(page.getByTestId('cart-count')).toHaveText(String(initial.total_item_count + 1))
    await expect(page.getByText(`可用库存 ${(before ?? 0) - 1} 件`)).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`pdp-${width}.png`), fullPage: true })
    const health = await request.get('/api/health')
    expect(health.status()).toBe(200)
    expect(await health.json()).toEqual({ status: 'ok', database: 'sqlite', stage: 'P0' })
    console.log(`E2E01 ${width}: real POST200, cart delta1, blue-L stock ${before}->${result.inventory.available_quantity}; no horizontal overflow`)
  })
}

test('E2E02 committed real response is discarded; browser reuses key and payload once', async ({ page, request }) => {
  const initial = parseCart(await (await request.get('/api/cart')).json())
  const product = parseProduct(await (await request.get('/api/products/p1')).json())
  const stock = product.skus.find(s => s.id === 'sku-red-s')?.available_quantity
  const attempts: { key: string | undefined; body: unknown }[] = []
  let original: unknown
  await page.route('**/api/cart/items', async route => {
    attempts.push({ key: route.request().headers()['idempotency-key'], body: route.request().postDataJSON() })
    if (attempts.length === 1) {
      const committed = await route.fetch() // forwards the REAL POST and waits for the committed response
      expect(committed.status()).toBe(200)
      original = await committed.json()
      const actual = parseCart(await (await request.get('/api/cart')).json())
      expect(actual.total_item_count).toBe(initial.total_item_count + 1) // prove commit BEFORE dropping
      await route.abort('failed') // no fabricated success is ever delivered to the page
    } else await route.continue()
  })
  await page.goto('/')
  await page.getByRole('button', { name: '红色', exact: true }).click()
  await page.getByRole('button', { name: 'S', exact: true }).click()
  await page.getByRole('button', { name: /加入购物车/ }).click()
  await expect(page.getByRole('button', { name: '重试确认本次加购' })).toBeVisible()
  await expect(page.getByLabel('数量')).toBeDisabled()
  // A read that already sees the increment must not unlock a new intent.
  await page.getByRole('button', { name: '刷新购物车' }).click()
  await expect(page.getByTestId('cart-count')).toHaveText(String(initial.total_item_count + 1))
  await expect(page.getByRole('button', { name: '重试确认本次加购' })).toBeVisible()
  const replay = page.waitForResponse(response => response.url().endsWith('/api/cart/items'))
  await page.getByRole('button', { name: '重试确认本次加购' }).click()
  const response = await replay
  expect(response.status()).toBe(200)
  expect(await response.json()).toEqual(original)
  await expect(page.getByText('本次已成功加入 1 件商品。')).toBeVisible()
  expect(attempts).toHaveLength(2); expect(attempts[1]).toEqual(attempts[0])
  expect(attempts[0]?.key).toMatch(/^[0-9a-f-]{36}$/)
  const finalCart = parseCart(await (await request.get('/api/cart')).json())
  const finalProduct = parseProduct(await (await request.get('/api/products/p1')).json())
  expect(finalCart.total_item_count).toBe(initial.total_item_count + 1)
  expect(finalProduct.skus.find(s => s.id === 'sku-red-s')?.available_quantity).toBe((stock ?? 0) - 1)
  console.log('E2E02 real POST200 committed -> transport abort -> same key/payload replay200; cart/stock delta exactly1')
})

test('E2E03 stale page loses last unit to another real request and recovers stock state', async ({ page, request }) => {
  const initial = parseCart(await (await request.get('/api/cart')).json())
  await page.goto('/')
  await page.getByRole('button', { name: '红色', exact: true }).click()
  await expect(page.getByRole('button', { name: 'L · 售罄', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'XL', exact: true }).click()
  await expect(page.getByText('可用库存 1 件')).toBeVisible()
  const winner = await request.post('/api/cart/items', { headers: { 'Idempotency-Key': randomUUID() }, data: { sku_id: 'sku-red-xl', quantity: 1 } })
  expect(winner.status()).toBe(200)
  const post = page.waitForResponse(response => response.url().endsWith('/api/cart/items') && response.request().method() === 'POST')
  await page.getByRole('button', { name: /加入购物车/ }).click()
  const loser = await post
  expect(loser.status()).toBe(409)
  const failure: unknown = await loser.json()
  expect(failure).toMatchObject({ error: { code: 'INSUFFICIENT_STOCK' } })
  await expect(page.getByText(/库存不足，本次未加入/)).toBeVisible()
  await expect(page.getByText(/此规格已售罄/)).toBeVisible()
  await expect(page.getByRole('button', { name: /加入购物车/ })).toBeDisabled()
  await page.getByRole('button', { name: '刷新购物车' }).click()
  await expect(page.getByTestId('cart-count')).toHaveText(String(initial.total_item_count + 1))
  const cart = parseCart(await (await request.get('/api/cart')).json())
  expect(cart.total_item_count).toBe(initial.total_item_count + 1)
  await page.getByRole('button', { name: '清空选择' }).click()
  await expect(page.getByText(/请选择颜色和尺寸/)).toBeVisible()
  console.log('E2E03 another real POST wins redXL; stale page POST409 -> out_of_stock, cart delta1, clear recovers selection')
})

for (const width of [375, 1280]) {
  test(`FE12 keyboard main flow and retry at ${width}px`, async ({ page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const initial = parseCart(await (await request.get('/api/cart')).json())
    let allowProduct = false
    await page.route('**/api/products/p1', async route => {
      if (!allowProduct) await route.abort('failed')
      else await route.continue()
    })
    await page.goto('/')
    await expect(page.getByRole('alert')).toContainText('商品加载失败')
    // Locate via actual Tab traversal, not focus() or DOM-only attributes.
    const retry = page.getByRole('button', { name: '重试读取商品' })
    for (let i = 0; i < 15 && !await retry.evaluate(el => el === document.activeElement); i++) await page.keyboard.press('Tab')
    await expect(retry).toBeFocused()
    const outline = await retry.evaluate(el => ({ style: getComputedStyle(el).outlineStyle, width: getComputedStyle(el).outlineWidth }))
    expect(outline.style).toBe('solid'); expect(outline.width).toBe('3px')
    allowProduct = true
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: 'Variant Demo Tee' })).toBeVisible()
    // Focus stays on the retry control after the asynchronous load; no autofocus jumps.
    await expect(page.getByRole('button', { name: '刷新商品库存' })).toBeFocused()
    await page.keyboard.press('Tab') // red
    await page.keyboard.press('Tab') // blue
    await expect(page.getByRole('button', { name: '蓝色', exact: true })).toBeFocused()
    await page.keyboard.press('Space')
    await page.keyboard.press('Tab') // S
    await page.keyboard.press('Tab') // M
    await expect(page.getByRole('button', { name: 'M', exact: true })).toBeFocused()
    await page.keyboard.press('Enter')
    await page.keyboard.press('Tab') // L, XL disabled
    await page.keyboard.press('Tab') // clear
    await page.keyboard.press('Tab') // quantity
    await expect(page.getByLabel('数量')).toBeFocused()
    await page.keyboard.press('ControlOrMeta+A'); await page.keyboard.type('1')
    await page.keyboard.press('Shift+Tab'); await expect(page.getByRole('button', { name: '清空选择' })).toBeFocused()
    await page.keyboard.press('Tab'); await page.keyboard.press('Tab')
    const submit = page.getByRole('button', { name: /加入购物车/ })
    await expect(submit).toBeFocused()
    const keys: string[] = []
    await page.route('**/api/cart/items', async route => {
      keys.push(route.request().headers()['idempotency-key'] ?? '')
      const response = await route.fetch()
      await new Promise(resolve => setTimeout(resolve, 150)) // holds only the response, after real commit
      await route.fulfill({ response })
    })
    await page.keyboard.press('Enter'); await page.keyboard.press('Enter')
    await expect(page.getByText('本次已成功加入 1 件商品。')).toBeVisible()
    await expect(page.getByTestId('cart-count')).toHaveText(String(initial.total_item_count + 1))
    expect(keys).toHaveLength(1)
    await expect(page.getByText('本次已成功加入 1 件商品。')).toHaveAttribute('role', 'status')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`keyboard-${width}.png`), fullPage: true })
    console.log(`FE12 ${width}: actual Tab/Shift+Tab/Space/Enter, visible focus, local retry, repeated Enter one real POST; status semantics checked (not screen reader hardware)`)
  })
}
