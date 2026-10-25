import { useState } from 'react'
import type { AddCartItemRequest, Product } from '../api/contracts'
import { clampQuantity, optionAvailability, parseQuantity, resolveVariant } from '../domain/variants'
import type { Selection } from '../domain/variants'

const labels: Record<string, string> = { color: '颜色', size: '尺寸', red: '红色', blue: '蓝色' }
const label = (value: string) => labels[value] ?? value
const money = (price: number) => new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(price / 100)
interface Props { product: Product; locked: boolean; rejectedPayload: string; onSubmit: (payload: AddCartItemRequest) => void }

export function ProductForm({ product, locked, rejectedPayload, onSubmit }: Props) {
  const [selection, setSelection] = useState<Selection>({})
  const variant = resolveVariant(product, selection)
  const sku = 'sku' in variant ? variant.sku : null
  const maximum = variant.kind === 'available' ? variant.sku.available_quantity : 0
  const basis = `${sku?.id ?? ''}:${maximum}`
  const [draft, setDraft] = useState({ basis, text: '1', adjusted: false })
  // Clamp in the render deriving the new SKU, so no frame mixes an old quantity with a new limit.
  const quantityText = draft.basis !== basis ? clampQuantity(draft.text, maximum) : draft.text
  if (draft.basis !== basis) setDraft({ basis, text: quantityText,
    adjusted: maximum > 0 && quantityText !== draft.text })
  const quantity = parseQuantity(quantityText, maximum)
  const payload = sku && quantity ? { sku_id: sku.id, quantity } : null
  const rejected = payload && JSON.stringify(payload) === rejectedPayload
  const prices = product.skus.map(item => item.price_minor)
  const price = sku ? money(sku.price_minor) : `${money(Math.min(...prices))} – ${money(Math.max(...prices))}`
  const stockMessage = variant.kind === 'incomplete' ? '请选择颜色和尺寸，查看对应价格与库存。'
    : variant.kind === 'invalid' ? '此组合不提供，请清空选择后重新选择。'
    : variant.kind === 'out_of_stock' ? '此规格已售罄，请选择其他规格。'
    : `可用库存 ${maximum} 件`

  function choose(name: string, value: string) {
    setSelection(old => ({ ...old, [name]: value }))
    setDraft({ basis, text: quantityText, adjusted: false })
  }
  return <div className="product-layout">
    <div className="product-art">
      <span className="art-caption">EVERYDAY / 01</span>
      <img src={sku?.image_url ?? product.images[0]} alt={sku
        ? `${product.name}，${product.options.map(option => label(sku.option_values[option.name] ?? '')).join(' / ')}`
        : `${product.name} 商品主图`} />
      <p>两种颜色 · 四种尺寸</p>
    </div>
    <section className="product-info" aria-labelledby="product-title">
      <p className="eyebrow">THE ESSENTIAL COLLECTION</p>
      <h1 id="product-title">{product.name}</h1>
      <p className="description">{product.description}</p>
      <p className="price" aria-label="价格">{price}</p>
      {!sku && <p className="muted">选定规格后显示准确单价</p>}
      <p className={`stock stock-${variant.kind}`} role="status" aria-live="polite">{stockMessage}</p>
      <form noValidate onSubmit={event => {
        event.preventDefault()
        if (!locked && variant.kind === 'available' && payload && !rejected) onSubmit(payload)
      }} aria-label="商品规格与加购" aria-busy={locked}>
        {product.options.map(option => <fieldset key={option.name} disabled={locked}>
          <legend>{label(option.name)} <span>{selection[option.name] ? label(selection[option.name] ?? '') : '尚未选择'}</span></legend>
          <div className="option-list">
            {option.values.map(value => {
              const availability = optionAvailability(product, selection, option.name, value)
              const suffix = availability === 'unavailable' ? ' · 不提供' : availability === 'out_of_stock' ? ' · 售罄' : ''
              return <button key={value} type="button" className={`option ${option.name === 'color' ? 'color-option' : ''}`}
                aria-pressed={selection[option.name] === value} disabled={availability !== 'available'}
                onClick={() => choose(option.name, value)}>
                {option.name === 'color' && <span className={`swatch swatch-${value}`} aria-hidden="true" />}
                {label(value)}{suffix}
              </button>
            })}
          </div>
        </fieldset>)}
        <button type="button" className="text-button" disabled={locked} onClick={() => {
          setSelection({}); setDraft({ basis: '', text: '1', adjusted: false })
        }}>清空选择</button>
        <div className="quantity-row">
          <label htmlFor="quantity">数量</label>
          <input id="quantity" name="quantity" type="text" inputMode="numeric" autoComplete="off"
            value={quantityText} disabled={locked || variant.kind !== 'available'}
            aria-invalid={variant.kind === 'available' && quantity === null} aria-describedby="quantity-help"
            onChange={event => setDraft({ basis, text: event.target.value, adjusted: false })} />
          <p id="quantity-help">{maximum > 0 ? `请输入 1–${maximum} 的整数` : '选定有库存的规格后可调整数量'}</p>
        </div>
        {draft.adjusted && maximum > 0 && <p role="status">数量已按当前库存调整为 {quantityText}。</p>}
        {variant.kind === 'available' && quantity === null && <p role="alert">数量无效，请输入库存范围内的正整数。</p>}
        {rejected && <p className="muted">请修改规格或数量后再提交。</p>}
        <button className="primary-button" type="submit" disabled={locked || variant.kind !== 'available' || !quantity || !!rejected}>
          {locked ? '等待本次加购确认' : '加入购物车'}<span aria-hidden="true">↗</span>
        </button>
      </form>
      <p className="purchase-note">加入购物车后会暂时预留库存。</p>
    </section>
  </div>
}
