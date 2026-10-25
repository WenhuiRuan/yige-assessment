import { ProductForm } from './components/ProductForm'
import { useProductPage } from './pages/useProductPage'

export function App() {
  const page = useProductPage()
  return <>
    <header className="site-header">
      <a className="wordmark" href="#main">熠革 <span>YIGE / GOODS</span></a>
      <div className="cart-summary" aria-label="购物车摘要">
        <span>购物车</span><strong data-testid="cart-count">{page.cart ? page.cart.total_item_count : '未知'}</strong>
        {page.cartRead.loading && <span role="status">同步中…</span>}
        {page.cartRead.error && <p role="alert">购物车读取失败{page.cart ? '，显示上次确认件数' : '，件数未知'}。</p>}
        <button type="button" className="text-button" onClick={() => void page.refreshCart()}>刷新购物车</button>
      </div>
    </header>
    <main id="main">
      <nav aria-label="当前位置" className="breadcrumb">精选商品 <span aria-hidden="true">/</span> 日常系列</nav>
      <div className="read-controls">
        {page.productRead.loading && <p role="status">{page.inventory ? '正在同步最新商品库存…' : '正在加载商品…'}</p>}
        {page.productRead.error && <p role="alert">{page.inventory ? '最新库存同步失败，保留上次已知数据。' : '商品加载失败，请重试。'}</p>}
        <button className="text-button" type="button" onClick={() => void page.refreshProduct()}>
          {page.productRead.error ? '重试读取商品' : '刷新商品库存'}
        </button>
      </div>
      {page.inventory && <ProductForm product={page.inventory.product} locked={page.locked}
        rejectedPayload={page.rejectedPayload} onSubmit={page.submit} />}
      <section className="operation-feedback" aria-label="本次加购反馈" aria-busy={page.add.kind === 'submitting'}>
        <p role="status" aria-live="polite">{['submitting', 'success'].includes(page.add.kind) ? page.add.message : ''}</p>
        {['rejected', 'uncertain', 'conflict'].includes(page.add.kind) && <p role="alert">{page.add.message}</p>}
        {page.add.kind === 'uncertain' && <button className="primary-button" onClick={page.retryPending}>重试确认本次加购</button>}
      </section>
    </main>
    <footer>YIGE / GOODS</footer>
  </>
}
