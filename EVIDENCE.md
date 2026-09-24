# Acceptance Evidence

## 1. Exactly-Once Metering

`usage_events` enforces a unique `(tenant_id, idempotency_key)` constraint.

`record_usage()` also checks for an existing event inside a database transaction before inserting. Repeating a request with the same tenant and idempotency key returns the existing event instead of charging usage again.

Final acceptance output will be recorded during the final test pass.

## 2. Exact Quota Boundary

The documented boundary is inclusive:

- usage exactly equal to the monthly limit is allowed;
- the first request that would exceed the limit returns HTTP 429.

Free limits are 1,000 API calls and 100,000 AI tokens per month.

Pro limits are 10,000 API calls and 1,000,000 AI tokens per month.

Final boundary output will be recorded during the final test pass.

## 3. Stripe Checkout: Free to Pro

A Stripe sandbox/test Checkout was completed successfully.

Before Checkout, the demo tenant was on Free.

After the valid `checkout.session.completed` webhook, `GET /usage` reported:

```text
plan = Pro
api_call_limit = 10000
ai_token_limit = 1000000
```

No live Stripe payment mode is used.

## 4. Webhook Verification and Replay Protection

An unsigned request to `/webhooks/stripe` returned HTTP 400 with `Missing Stripe signature`.

A genuine Stripe Checkout event was replayed using Stripe CLI.

The database count for that Stripe event ID remained:

```text
Stored copies: 1
```

This demonstrates webhook event deduplication.

## 5. Token Pricing and Cost Rollup

The pricing test recorded:

```text
input_tokens        = 1000
cached_input_tokens = 1000
output_tokens       = 1000
reasoning_tokens    = 1000
```

The stored usage event contained:

```text
quantity = 4000
cost_microdollars = 5330
```

`GET /usage?tenant_id=1` subsequently reported:

```text
ai_tokens.used = 4000
input_tokens = 1000
cached_input_tokens = 1000
output_tokens = 1000
reasoning_tokens = 1000
monthly_total = 5330
```

The API rollup therefore matched the deterministic pricing calculation.

## Migrations and Indexes

A clean temporary database successfully applied:

```text
001_initial.sql
002_add_token_cost_fields.sql
```

The final `usage_events` schema contained the four token-category columns and `cost_microdollars`.

Indexes included:

```text
idx_usage_tenant_type_created
idx_usage_tenant_created
```

## Background Job

`python background_jobs.py` successfully reconciled one tenant.

The observed monthly totals included 4,000 AI tokens at 5,330 microdollars and three API calls.

The worker runs independently from the HTTP request path and implements three retry attempts plus critical failure logging.

## Final Acceptance Pass

### Idempotency Probe

First duplicate: False  
Second duplicate: True  
Stored events: 1

The same tenant-scoped idempotency key was submitted twice. The second request returned the existing event and only one database row was stored.

### Exact Free-Plan Boundary Probe

The idempotency test first consumed one API call. A subsequent request for 999 calls was accepted, bringing monthly usage to exactly the Free-plan limit of 1,000.

Boundary quantity: 999  
Boundary error: None  
Next request status: 429  
Next request error: Monthly usage quota exceeded

This confirms that the exact limit is permitted and the first request beyond the limit is rejected.
