# Task C - Xero Integration Review

[中文版](answers.md)

This solution uses OAuth 2.0 Authorization Code with `offline_access` and the Accounting API at `/api.xro/2.0`. The answers describe HTTP requests rather than a specific SDK.

## C1 - Connection verification

I would perform three checks in order:

1. Validate state in the authorization callback, then exchange the code at `https://identity.xero.com/connect/token`. On success, save the access/refresh tokens, expiry time, and granted scopes. This confirms that the OAuth authorization exchange completed.
2. Use the access token to call `GET https://api.xero.com/connections`. Confirm that the returned list contains the target organization. Stop if the list is empty; do not simply select the first organization by default.
3. Check the returned tenantId against the internal organization mapping. Use `xero-tenant-id` in subsequent Accounting requests. The connection id and tenantId are different fields.

If settings read permission is already granted, GET Organisation can provide another organization ID check before reading invoices. Successful connection and organization queries prove only that those accesses work. Reading invoices still requires the granted `accounting.invoices.read` scope; an id token cannot replace an access token.

## C2 - Failure diagnosis

First compare the working and failing environments: outbound URL, HTTP method, client configuration, the authorization associated with the token, scopes, and tenant header. Then investigate by status:

| Result | Next step |
| --- | --- |
| 401 | Check token expiry, token type, and whether authorization was revoked. If expired, refresh under a lock and replay at most once. If it still fails or returns invalid_grant, pause the job and request reauthorization. |
| 403 | Check for a missing tenant header or a connection id mistakenly used as the tenant ID. Verify that the target organization belongs to the authorization, then check granted scopes, user roles, and organization/subscription status. Missing permissions require reauthorization or administrator action; refreshing a token does not add permissions. |
| 404 | Check the API path, method, InvoiceID, and organization. If listing works but a single-resource request fails, check the resource mapping. If the entire endpoint fails, check environment variables, proxy rewriting, and dropped headers. |

Interpret status codes together with the response body: an HTML 403, for example, may come from a proxy. Also compare old and new scopes across environments. An older application's transactions permission does not prove that a newer application has been granted invoices permission.

## C3 - Incremental synchronisation

For each tenant, store the last successful scan time, the current run's start time T0, query conditions, and next-page position. Allow only one invoice synchronization job per tenant. Start with a paginated full read. For later runs, use `If-Modified-Since` with a lower bound slightly before the last successful scan time to provide an overlap window. Use the same ordering on each page; pageSize=100 is a reasonable starting value.

After reading a page successfully, update invoices by `(tenantId, InvoiceID)` and save progress in the same database transaction. On failure, keep the previous checkpoint and reread on recovery. The unique key merges repeated records; downstream operations additionally use business keys for deduplication. Older updates must not overwrite newer records, and different invoices sharing a timestamp must all be processed. Advance the successful scan time to T0 only after every page is complete.

Data may change during pagination. After a long interruption or a detected shift in page positions, restart from the original time lower bound. Reconcile periodically by ID or with a full scan to recover omissions; overlap alone does not replace reconciliation. Synchronization must also update states such as voided and deleted. An invoice missing from one page is not sufficient reason to delete the local record.

## C4 - Rate limits

On 429, read `Retry-After`, `X-Rate-Limit-Problem`, `X-MinLimit-Remaining`, `X-DayLimit-Remaining`, and `X-AppMinLimit-Remaining`. Wait at least Retry-After, then add random jitter. Use capped exponential backoff for repeated failures. If wait information is missing, back off conservatively rather than immediately looping.

All workers share per-tenant concurrency limits and request budgets, while also enforcing the application-wide allowance. Exhausting a tenant's budget pauses only that tenant; exhausting the application's budget limits dispatch across the application. Save the next execution time and let the scheduler handle long waits without occupying a worker. Bound both retry count and total elapsed time, continue counting after requeuing, and alert when limits are exceeded.

Do not retry unchanged requests for validation errors, 403, definitive 404, 501, or idempotency conflicts. Handle 401 as described in C2. Retry 429, temporary network errors, and 500/503 within limits, but first check creation safety as described in C5. Even when a batch returns 200, inspect each item for errors and process only unsuccessful items.

## C5 - Data integrity

Before creation, persist a local operation for the order with a unique constraint on `(tenantId, internal_order_id, operation_type)`. Record the request-content digest, idempotency key, first-send time, and status. Concurrent retries share the same operation. For an order already created successfully, return the saved InvoiceID instead of creating it again.

Xero idempotency keys have a maximum length of 128 characters and a six-minute cache window; internal errors may also be cached. On timeout or a lost response, mark the outcome as unknown. Within that window, retry with the original method, URL, key, and body to confirm the result.

After the window expires, query and reconcile before taking further action; do not create again with a new key. Search by an existing InvoiceID or business identifier, then compare organization, type, contact, amount, and currency. If exactly one matching record is found, save the mapping. Multiple matches or inconsistencies require manual review. A single unsuccessful lookup does not prove that creation failed. Reference is not guaranteed to be unique; InvoiceNumber must be unique for ACCREC but not for ACCPAY. If the outcome remains uncertain, retain the unknown state and stop automatic creation.

## C6 - Observability and security

Log a masked organization identifier, job/run/operation/request IDs, endpoint, status code, duration, retry count, and synchronization page position. Retain Xero's `Xero-Correlation-Id` to connect a business operation to its remote requests.

Monitor synchronization lag, backlog, failed pages, reconciliation differences, 429 responses, refresh failures, and the count and maximum waiting time of creation operations with unknown outcomes. Alert on persistent failures, excessive lag, or unknown operations extending beyond the idempotency window. Arrange reauthorization, rereading, or manual reconciliation as appropriate.

Do not log tokens, client secrets, Authorization headers, OAuth codes, full callback URLs, or complete customer, invoice, or bank data. Encrypt stored credentials, keep encryption keys in a separate secrets management service, restrict access, and rotate regularly. Restrict log access and retention as well.

Use a cross-process lock on the actual shared authorization record during refresh, preventing duplicate refreshes when several organizations share an authorization. Inside the lock, reread the credential version and atomically save the new access/refresh tokens and expiry time. A version condition prevents an older job from overwriting newer credentials. Each job explicitly carries its tenantId and authorization reference and checks their mapping before execution. Pause jobs and request reauthorization when authorization becomes invalid.

## References

1. [OAuth authorization and refresh](https://developer.xero.com/documentation/guides/oauth2/auth-flow/)
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
