# 熠革科技全栈笔试

[English version](README.en.md)

- [A](A/README.md)：库存预留程序、复杂度说明和测试。
- [B](B/README.md)：多仓分配程序、算法说明和测试。
- [C](C/answers.md)：Xero 六问回答。
- `app/`：FastAPI 后端与 React/TypeScript 商品页。

## 安装和运行

需要 Python 3.11+、Node 24.x（≥24.15）、npm≥10。已验证环境为 Windows / Python 3.12.10 / Node 24.18.0 / npm 10.5.0。

主要依赖：FastAPI、Pydantic、Uvicorn；React、TypeScript、Vite。测试使用 pytest/HTTPX、Vitest/Testing Library/MSW、Playwright；SQLite 来自 Python 标准库。版本见 `requirements-dev.txt` 和 `app/frontend/package-lock.json`。

在仓库根目录，PowerShell 终端一执行：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```

终端二从仓库根目录执行：

```powershell
cd app/frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

访问 [商品页](http://127.0.0.1:5173)；[接口文档](http://127.0.0.1:8000/docs) 可辅助调试。Ctrl+C 停止服务。Bash 使用 `.venv/bin/python` 和 `npm`；其他系统未实测。

启动自动建表和初始化商品 p1：红/蓝两色、S/M/L/XL 四尺寸，共7个SKU；蓝XL不存在，红L售罄。数据保存在 `data/yige.sqlite3`，重启保留。需要清空演示记录时，停止后端，在仓库根运行 `.venv/Scripts/python.exe -m app.backend.seed --reset`，重启并重新加载页面。

环境变量：`YIGE_DB_PATH` 指定数据库路径，`YIGE_API_TARGET` 指定前端代理目标（默认 `http://127.0.0.1:8000`）。`.env.example` 仅作说明，不自动加载 .env。

## 测试

先完成上面的 Python 和前端依赖安装，再打开新终端运行。A、B 和后端测试均在仓库根目录执行。

**A：库存预留程序**。验证预留、释放、发货、补货，库存和订单边界、非法输入、事件重放及大规模输入。

```powershell
.venv/Scripts/python.exe -m pytest A/tests -q
```

**B：多仓分配算法**。验证仓库数和费用最优、同优时的字典序选择，以及无解、零需求和大规模输入。

```powershell
.venv/Scripts/python.exe -m pytest B/tests -q
```

**C：Xero 书面回答**。见 [C/answers.md](C/answers.md)，无自动化测试。

**全栈应用后端**。验证接口参数和错误响应、购物车金额、幂等重放、并发防超卖、事务回滚及重启后的数据保留。

```powershell
.venv/Scripts/python.exe -m pytest app/backend/tests -q
```

如需一次运行以上 A、B 和后端的全部 Python 测试，可用下面的命令代替三条分项命令，无需重复运行：

```powershell
.venv/Scripts/python.exe -m pytest -q
```

**前端测试**：从仓库根目录进入前端目录运行，验证规格切换后的图片、价格和库存，缺失组合与售罄状态、数量限制、防重复提交，以及加载失败、超时重试和旧响应处理。

```powershell
cd app/frontend
npm.cmd run test -- --run
```

**端到端测试**：继续在前端目录执行，通过 Chromium 连接真实后端，验证选规格和加购、响应丢失后的重试、最后一件库存被抢占后的处理，以及 375px/1280px 页面布局和键盘操作。测试自动启动隔离服务，使用临时 SQLite 数据库和 18000/15173 端口。

```powershell
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

**代码检查和构建**：Ruff、ESLint 检查代码规范，typecheck 检查 TypeScript 类型，build 验证前端能否完成生产构建。

仓库根目录执行：

```powershell
.venv/Scripts/python.exe -m ruff check .
```

前端目录执行：

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

## API 示例

金额均为CNY整数分，购物车件数为商品数量之和。以下使用初始数据。

**GET /api/products/p1 → 200**。无请求体；响应示例节选（完整响应含7个SKU，下方仅列一个）：

```json
{
  "id": "p1",
  "name": "Variant Demo Tee",
  "description": "用于规格选择和库存预留演示的 T 恤",
  "currency": "CNY",
  "images": ["/images/product.svg"],
  "options": [
    {"name": "color", "values": ["red", "blue"]},
    {"name": "size", "values": ["S", "M", "L", "XL"]}
  ],
  "inventory_revision": 0,
  "skus": [
    {"id": "sku-red-s", "price_minor": 9900, "available_quantity": 5,
     "image_url": "/images/sku-red-s.svg", "option_values": {"color": "red", "size": "S"}}
  ]
}
```

**POST /api/cart/items**。只接受 sku_id 和正整数 quantity，价格与库存由服务器决定：

```http
POST /api/cart/items
Content-Type: application/json
Idempotency-Key: example-1

{"sku_id":"sku-red-s","quantity":1}
```

首次成功 **200**：

```json
{
  "cart": {
    "id":"demo","revision":1,"currency":"CNY",
    "items":[{"sku_id":"sku-red-s","quantity":1,"unit_price_minor":9900,"line_total_minor":9900}],
    "total_item_count":1,"total_price_minor":9900
  },
  "inventory":{"revision":1,"sku_id":"sku-red-s","available_quantity":4}
}
```

**GET /api/cart → 200**。无请求体；上述加购后的响应：

```json
{
  "id":"demo","revision":1,"currency":"CNY",
  "items":[{"sku_id":"sku-red-s","quantity":1,"unit_price_minor":9900,"line_total_minor":9900}],
  "total_item_count":1,"total_price_minor":9900
}
```

| 状态码 | 含义 |
| --- | --- |
| 200 | 查询或加购成功，同key同载荷重放返回原业务结果 |
| 404 | 商品或SKU不存在 |
| 409 | 库存不足，或同key用于不同请求 |
| 422 | 非法JSON、字段、数量或幂等key；不接受客户端price/stock |
| 500 / 503 | 意外错误 / 数据库暂时不可用 |

错误统一为 `error` 对象，例如库存不足：

```json
{
  "error": {
    "code":"INSUFFICIENT_STOCK","message":"Requested quantity exceeds available stock",
    "details":{"sku_id":"sku-red-xl","requested_quantity":2,"available_quantity":1,"inventory_revision":0},
    "request_id":"example-request-id"
  }
}
```

幂等key为1–128个非空白可打印ASCII字符。正常业务响应带 `X-Request-ID` 和 `Cache-Control: no-store`。相同key不会重复加购；更换请求内容必须使用新操作。

## 架构、假设与限制

- 后端按路由、服务、数据访问拆分；每请求独立SQLite连接。加购解释为预留库存，在库数量不变，可用量减少。`BEGIN IMMEDIATE` 事务内通过带库存条件的UPDATE防超卖，购物车、版本与幂等结果一同提交，异常整体回滚。
- 成功及确定的SKU不存在/库存不足结果持久化；格式错误和500/503不缓存。同key不同合法请求返回409。
- 前端分为API、领域逻辑和UI。同步提交锁防双击；购物车和库存版本独立，旧响应不覆盖新状态。超时或响应丢失时保留原key/载荷重试，已成功加购后的读取失败只重试查询。
- 单个共享演示购物车，无用户隔离、预留释放或过期；幂等记录不清理，SQLite为单写者。未确认操作仅保存在当前页内存，确认前关闭页面会丢失该重试上下文。
- 未实现题目范围外的认证、结算、支付和生产部署；可选的乐观UI、分析事件和容器化未做。

## AI 使用披露

Full-Stack App项目中，AI 协助搭建 FastAPI 与 React/TypeScript 工程，编写常规接口、页面组件和样式。

测试与交付环节，AI 协助编写和补充自动化测试。AI 协助整理文档，我确认命令、说明和代码一致。
