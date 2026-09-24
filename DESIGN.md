# Usage Metering & Billing Engine — Design

## Problem

SaaS products need to know how much each customer has used, whether they are still within their subscription limits, and what that usage costs. This service will provide a small multi-tenant billing backend that records billable usage, enforces plan quotas, calculates costs, and keeps subscription state synchronized with Stripe in test mode.

The main correctness requirement is that retries must never cause usage to be counted twice.

## Scope

The system will support:

- Two plans: Free and Pro
- Two usage types: API calls and AI tokens
- One dummy billable endpoint: `POST /generate`
- Monthly quota enforcement
- Usage and cost reporting
- Stripe Checkout in test mode
- Verified and idempotent Stripe webhooks

### Plan Limits

| Plan | API Calls / Month | AI Tokens / Month |
|---|---:|---:|
| Free | 1,000 | 100,000 |
| Pro | 10,000 | 1,000,000 |

The Pro limits are project-defined and intentionally higher than the Free plan.

## Data Model

### tenants

Represents a customer organisation.

- `id`
- `name`
- `created_at`

### plans

Defines available subscription plans and their quotas.

- `id`
- `name`
- `api_call_limit`
- `ai_token_limit`

### subscriptions

Stores the current subscription state for each tenant.

- `id`
- `tenant_id`
- `plan_id`
- `status`
- `stripe_customer_id`
- `stripe_subscription_id`
- `created_at`
- `updated_at`

### usage_events

Stores individual billable actions.

- `id`
- `tenant_id`
- `usage_type`
- `quantity`
- `idempotency_key`
- `created_at`

The combination of tenant and idempotency key will be unique so the same request cannot create multiple usage events.

### stripe_events

Stores processed Stripe webhook event IDs.

- `id`
- `stripe_event_id`
- `event_type`
- `processed_at`

`stripe_event_id` will be unique so replayed Stripe webhooks are processed only once.

## API Surface

### `GET /health`

Confirms that the service is running.

### `POST /generate`

Dummy billable action.

The request identifies a tenant, provides simulated usage, and includes an idempotency key.

Flow:

1. Validate the request.
2. Look for an existing event with the same tenant and idempotency key.
3. If one exists, return the original result without recording new usage.
4. Calculate the tenant's current monthly usage.
5. Check the requested usage against the tenant's plan quota.
6. Reject the request with a clear `429` or `402` response when appropriate.
7. Otherwise record one usage event.
8. Return the successful result.

### `GET /usage`

Returns a tenant's current monthly usage, limits, and calculated cost.

### `POST /checkout`

Creates a Stripe Checkout session for upgrading to Pro in Stripe test mode.

### `POST /webhooks/stripe`

Receives Stripe webhook events.

The endpoint will verify the Stripe signature before processing the event, deduplicate events using the Stripe event ID, and update subscription state when relevant events are received.

## Idempotency Strategy

Every billable request must include an idempotency key.

A unique database constraint on `(tenant_id, idempotency_key)` will provide the final guarantee against duplicate usage records. Before inserting an event, the service will also check whether that key has already been processed.

If the same request is retried with the same key, the service returns the existing result instead of creating another usage event.

Stripe webhooks have a separate idempotency mechanism. Processed Stripe event IDs are stored in `stripe_events`, and a duplicate event ID is ignored.

## Quota Boundary

Quota checks happen before recording new usage.

A request is allowed when:

`current usage + requested usage <= plan limit`

A request that would take usage above the limit is rejected. Therefore, a request that reaches the limit exactly is allowed, while the next billable request is rejected.

## Architecture

Client
→ FastAPI HTTP Layer
→ Service Layer
   - Metering / Idempotency
   - Quota Enforcement
   - Cost Calculation
   - Subscription Logic
→ Data Layer
→ Database

Stripe Checkout
→ Stripe
→ signed webhook
→ POST /webhooks/stripe
→ signature verification + deduplication
→ Subscription State

The HTTP, business-logic, and persistence responsibilities will remain separated so billing rules are not embedded directly inside route handlers.

## Money and Pricing

Money will be represented using integers rather than floating-point values.

AI token pricing will distinguish between:

- input tokens
- cached input tokens
- output tokens
- reasoning tokens

Cached input tokens will use their own cheaper rate, and reasoning tokens will be charged using the output-token rate. Pricing constants will be stored in configuration rather than scattered through application code.

## Explicit Non-Goal

The core project will not implement real-money payments, invoicing, proration, or overage billing.

Stripe will remain entirely in test mode. The goal is to demonstrate correct metering, quota enforcement, cost calculation, and subscription synchronization rather than build a complete commercial billing platform.
