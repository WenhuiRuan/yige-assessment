import { useCallback, useEffect, useRef, useState } from 'react'
import { addCartItem, ApiFailure, getCart, getProduct } from '../api/client'
import type { AddCartItemRequest, Cart } from '../api/contracts'
import { integer, record } from '../api/validation'
import { mergeCart, mergeInventory, mergeProduct } from '../domain/versions'
import type { InventoryState } from '../domain/versions'

interface ReadState { loading: boolean; error: boolean }
interface Operation { key: string; payload: AddCartItemRequest }
type AddState = { kind: 'idle' | 'submitting' | 'success' | 'rejected' | 'uncertain' | 'conflict'; message: string }

export function useProductPage() {
  const [inventory, setInventory] = useState<InventoryState | null>(null)
  const [cart, setCart] = useState<Cart | null>(null)
  const [productRead, setProductRead] = useState<ReadState>({ loading: true, error: false })
  const [cartRead, setCartRead] = useState<ReadState>({ loading: true, error: false })
  const [add, setAdd] = useState<AddState>({ kind: 'idle', message: '' })
  const [rejectedPayload, setRejectedPayload] = useState('')
  const pending = useRef<Operation | null>(null)
  const sending = useRef(false) // Synchronous lock before React's next render.
  const mounted = useRef(false)
  const productRequest = useRef({ sequence: 0, controller: new AbortController() })
  const cartRequest = useRef({ sequence: 0, controller: new AbortController() })

  const refreshProduct = useCallback(async () => {
    productRequest.current.controller.abort()
    const sequence = ++productRequest.current.sequence
    const controller = new AbortController()
    productRequest.current.controller = controller
    setProductRead({ loading: true, error: false })
    try {
      const product = await getProduct(controller.signal)
      if (mounted.current && sequence === productRequest.current.sequence) {
        setInventory(old => mergeProduct(old, product))
        setProductRead({ loading: false, error: false })
      }
    } catch {
      if (mounted.current && sequence === productRequest.current.sequence)
        setProductRead({ loading: false, error: true })
    }
  }, [])

  const refreshCart = useCallback(async () => {
    cartRequest.current.controller.abort()
    const sequence = ++cartRequest.current.sequence
    const controller = new AbortController()
    cartRequest.current.controller = controller
    setCartRead({ loading: true, error: false })
    try {
      const next = await getCart(controller.signal)
      if (mounted.current && sequence === cartRequest.current.sequence) {
        setCart(old => mergeCart(old, next))
        setCartRead({ loading: false, error: false })
      }
    } catch {
      if (mounted.current && sequence === cartRequest.current.sequence)
        setCartRead({ loading: false, error: true })
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refreshProduct(); void refreshCart()
    const product = productRequest.current
    const cart = cartRequest.current
    return () => {
      mounted.current = false
      ++product.sequence; ++cart.sequence
      product.controller.abort(); cart.controller.abort()
      // Cancelled waiting is never evidence that a POST was rolled back.
    }
  }, [refreshProduct, refreshCart])

  async function send(operation: Operation) {
    if (sending.current) return
    sending.current = true
    pending.current = operation
    setAdd({ kind: 'submitting', message: '正在确认加购，请稍候…' })
    try {
      const response = await addCartItem(operation.payload, operation.key)
      if (response.inventory.sku_id !== operation.payload.sku_id) throw new ApiFailure('protocol', 200)
      if (!mounted.current) return
      setCart(old => mergeCart(old, response.cart))
      setInventory(old => mergeInventory(old, response.inventory))
      pending.current = null
      setRejectedPayload('')
      setAdd({ kind: 'success', message: `本次已成功加入 ${operation.payload.quantity} 件商品。` })
      // GET failures do not reverse a confirmed POST success.
      void refreshProduct(); void refreshCart()
    } catch (error) {
      if (!mounted.current) return
      const failure = error instanceof ApiFailure ? error : null
      const code = failure?.response?.error.code
      if (code === 'IDEMPOTENCY_CONFLICT') {
        setAdd({ kind: 'conflict', message: '本次操作标识发生冲突。请核对购物车并重新加载页面；不会自动更换标识再次加购。' })
      } else if (failure?.kind === 'http' && (failure.status === 422 || failure.status === 404 || code === 'INSUFFICIENT_STOCK')) {
        pending.current = null
        if (code === 'INSUFFICIENT_STOCK') {
          const details = record(failure.response?.error.details)
          if (details.sku_id === operation.payload.sku_id) {
            setInventory(old => mergeInventory(old, { sku_id: operation.payload.sku_id,
              available_quantity: integer(details.available_quantity), revision: integer(details.inventory_revision) }))
          }
        }
        if (failure.status === 422) setRejectedPayload(JSON.stringify(operation.payload))
        setAdd({ kind: 'rejected', message: code === 'INSUFFICIENT_STOCK'
          ? '库存不足，本次未加入。已更新库存，请调整规格或数量后再试。'
          : failure.status === 422 ? '服务器拒绝了本次输入。请修改规格或数量后重新提交。'
          : '该规格已不存在，本次未加入。请刷新商品并重新选择。' })
        void refreshProduct()
      } else {
        // Includes timeout, disconnection, invalid JSON/response, 500 and 503.
        setAdd({ kind: 'uncertain', message: '暂时无法确认本次加购结果。请重试确认本次加购，不要创建新操作。' })
      }
    } finally { sending.current = false }
  }

  function submit(payload: AddCartItemRequest) {
    if (sending.current || pending.current || JSON.stringify(payload) === rejectedPayload) return
    void send({ key: crypto.randomUUID(), payload: { ...payload } })
  }
  function retryPending() {
    if (pending.current && add.kind === 'uncertain') void send(pending.current)
  }
  return { inventory, cart, productRead, cartRead, add, rejectedPayload, submit, retryPending,
    refreshProduct, refreshCart, locked: ['submitting', 'uncertain', 'conflict'].includes(add.kind) }
}
