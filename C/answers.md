# Task C - Xero Integration Review

采用 OAuth 2.0 Authorization Code 和 `offline_access`，调用 Accounting API `/api.xro/2.0`。以下按 HTTP 请求说明，不使用特定 SDK。

## C1 - Connection verification

我会依次做三项检查：

1. 校验授权回调的 state，再向 `https://identity.xero.com/connect/token` 交换 code。成功后保存 access/refresh token、到期时间及实际 scope，说明 OAuth 授权交换已完成。
2. 用 access token 调用 `GET https://api.xero.com/connections`。确认返回列表包含目标组织；空列表则停止，不能默认选择第一个组织。
3. 将返回的 tenantId 与内部组织绑定核对，后续 Accounting 请求使用 `xero-tenant-id`。connection id 和 tenantId 不是同一个字段。

如已有 settings 读取权限，可在读取发票前再 GET Organisation 核对组织 ID。连接和组织查询成功只能证明对应访问有效，发票读取仍需实际获授的 `accounting.invoices.read`；id token 不能代替 access token。

## C2 - Failure diagnosis

先比较正常环境和异常环境的出站 URL、方法、client 配置、token 所属授权、scope 和租户头，再按状态排查：

| 返回结果 | 下一步 |
| --- | --- |
| 401 | 检查 token 是否过期、类型是否正确、授权是否撤销。过期时加锁刷新并最多重放一次；仍失败或返回 invalid_grant，则暂停任务并要求重新授权。 |
| 403 | 检查租户头是否缺失或误填 connection id、目标组织是否属于该授权，再查实际 scope、用户角色及组织/套餐状态。缺权限需要重新授权或管理员处理，刷新 token 不会增加权限。 |
| 404 | 检查 API 路径、方法、InvoiceID 和所属组织。列表能读而单条失败时查资源映射；整个端点失败时查环境变量、代理重写及请求头是否丢失。 |

状态码要结合响应体判断，例如 HTML 403 可能来自代理。跨环境也要检查应用使用的新旧 scope，不能因为旧应用有 transactions 权限，就认为新应用的 invoices 权限已经获授。

## C3 - Incremental synchronisation

每个租户保存上次成功扫描的时间、本轮开始时间 T0、查询条件和下一页位置。同一租户只运行一个发票同步任务。首次分页全量读取；后续用 `If-Modified-Since` 读取上次时间之前一小段重叠窗口后的变更。每页使用相同排序，可先取 pageSize=100。

一页读取成功后，在同一数据库事务中按 `(tenantId, InvoiceID)` 更新发票并保存进度。失败则保留原检查点，恢复时重读；重复数据由唯一键合并，涉及下游操作时再用业务唯一键去重。旧更新时间不覆盖新记录，同时间戳的不同发票都处理。所有页完成后，才把成功扫描时间推进到 T0。

分页期间数据可能变化。长时间中断或发现页位变化时，从原时间下界重新扫描，并定期按 ID 或全量对账补漏。重叠窗口不能替代对账。同步也要更新作废、删除等状态，不能仅凭一页里没有某张发票就删除本地记录。

## C4 - Rate limits

收到 429 后，读取 `Retry-After`、`X-Rate-Limit-Problem` 和 `X-MinLimit-Remaining`、`X-DayLimit-Remaining`、`X-AppMinLimit-Remaining`。至少等待 Retry-After，再加随机抖动；连续失败使用有上限的指数退避。缺少等待信息时保守退避，不立即循环请求。

所有 worker 共享租户并发限制和请求预算，同时控制应用总额度。租户额度耗尽只暂停该租户，应用额度耗尽则限制整个应用派发。保存下次执行时间，长等待交给任务调度器，不占着 worker。重试次数和总耗时都设上限，重新入队后继续累计，超限告警。

参数校验错误、403、确定的404、501和幂等冲突不原样重试；401按C2处理。429、临时网络错误和500/503可以有限重试，但创建请求先按C5确认是否安全。批量请求即使返回200，也要逐项检查错误，只处理未成功的项。

## C5 - Data integrity

创建前，先在本地保存订单对应的操作，以 `(tenantId, internal_order_id, operation_type)` 做唯一约束，记录请求内容摘要、幂等 key、首次发送时间和状态。并发重试使用同一条操作；已成功的订单直接返回保存的 InvoiceID，不再次创建。

Xero 的幂等 key 最长128字符，有效缓存窗口为6分钟，内部错误也可能缓存。超时或响应丢失时，将操作标为结果未知；在窗口内用原方法、URL、key和请求体重试确认。

窗口过后先查询核对，不能换个 key 再创建。按已有 InvoiceID 或业务标识找记录，并比较组织、类型、联系人、金额和币种；唯一且一致就保存映射，多条或不一致转人工核查。一次查不到不能证明创建失败。Reference 没有唯一性保证；InvoiceNumber 在 ACCREC 中要求唯一，在 ACCPAY 中不要求唯一。仍无法确认时保留未知状态，停止自动创建。

## C6 - Observability and security

日志记录脱敏组织标识、job/run/operation/request ID、接口、状态码、耗时、重试次数和同步页位置，并保存 Xero 返回的 `Xero-Correlation-Id`，方便串起一次业务操作和远端请求。

监控同步延迟、积压、失败页、对账差异、429、刷新失败，以及未知创建操作的数量和最长等待时间。持续失败、延迟超限或未知操作超过幂等窗口时告警，分别安排重授权、补读或人工对账。

不记录 token、client secret、Authorization、OAuth code、完整回调 URL，以及完整客户、发票或银行数据。凭证加密保存，密钥放独立秘密管理服务，限制访问并定期轮换；日志也限制权限和保留时间。

刷新按实际共享的授权记录加跨进程锁，避免多个组织共用授权时重复刷新。锁内重新读取凭证版本，将新的 access/refresh token 与到期时间原子保存，通过版本条件防止旧任务覆盖新凭证。每个任务显式携带 tenantId 和授权引用，执行前核对绑定；授权失效后暂停任务并重新授权。

## 参考文档

1. [OAuth 授权与刷新](https://developer.xero.com/documentation/guides/oauth2/auth-flow/)
2. [Tenants](https://developer.xero.com/documentation/guides/oauth2/tenants/)
3. [Scopes](https://developer.xero.com/documentation/guides/oauth2/scopes/)
4. [Organisation](https://developer.xero.com/documentation/api/accounting/organisation/)
5. [Response Codes](https://developer.xero.com/documentation/api/accounting/responsecodes/)
6. [OAuth Troubleshooting](https://developer.xero.com/documentation/guides/oauth2/troubleshooting/)
7. [Invoices](https://developer.xero.com/documentation/api/accounting/invoices/)
8. [Requests and Responses](https://developer.xero.com/documentation/api/accounting/requests-and-responses/)
9. [Rate Limits](https://developer.xero.com/documentation/best-practices/api-call-efficiencies/rate-limits/)
10. [Idempotent Requests](https://developer.xero.com/documentation/guides/idempotent-requests/idempotency/)
11. [Managing Tokens](https://developer.xero.com/documentation/best-practices/data-integrity/managing-tokens/)
