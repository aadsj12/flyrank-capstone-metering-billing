# Build Log

## Phase 1 — Design

Defined the architecture, Free and Pro plans, tenant model, usage-event schema, idempotency strategy, quota semantics, API routes, Stripe workflow, and integer money model.

## Phase 2 — Core Metering

Implemented SQLite persistence, demo seed data, `/generate`, `/usage`, monthly quota enforcement, and tenant-scoped idempotency.

The quota boundary is inclusive: usage exactly equal to the limit is allowed, while a request that would exceed it is rejected.

## Phase 3 — Stripe

Added Stripe test-mode Checkout and webhook handling.

Implemented Checkout Session creation, Free-to-Pro upgrades, webhook signature verification, event persistence, duplicate-event suppression, and subscription lifecycle synchronization.

A completed sandbox Checkout successfully changed the demo tenant from Free to Pro. Replaying the same Stripe event left only one stored copy.

## Phase 4 — Cost Tracking

Added pinned Gemini 2.5 Flash token pricing using integer microdollars.

The system separately tracks input, cached-input, output, and reasoning tokens.

A deterministic test using 1,000 tokens in each category produced 5,330 microdollars, and `/usage` returned the same monthly cost.

## Persistence Hardening

Moved schema creation into versioned SQL migrations and added indexes for common tenant usage queries.

A clean temporary SQLite database successfully applied both migrations and seeded the demo environment.

## Background Processing

Added a standalone usage-reconciliation job that executes outside the HTTP request path.

The worker includes bounded retries and critical failure logging.

## Finalization

Added setup documentation, environment templates, dependency metadata, acceptance evidence, and reproducible local-run instructions.
