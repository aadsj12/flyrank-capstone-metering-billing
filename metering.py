import sqlite3

from database import get_connection


def record_usage(
    tenant_id: int,
    usage_type: str,
    quantity: int,
    idempotency_key: str,
):
    connection = get_connection()

    try:
        # Lock writes while we check idempotency, quota, and record usage.
        connection.execute("BEGIN IMMEDIATE")

        # 1. A retry must return the original event without charging again.
        existing_event = connection.execute(
            """
            SELECT id, tenant_id, usage_type, quantity,
                   idempotency_key, created_at
            FROM usage_events
            WHERE tenant_id = ? AND idempotency_key = ?
            """,
            (tenant_id, idempotency_key),
        ).fetchone()

        if existing_event:
            connection.commit()
            return {
                "event": dict(existing_event),
                "duplicate": True,
            }

        # 2. Find the tenant's active subscription and plan limits.
        subscription = connection.execute(
            """
            SELECT
                subscriptions.status,
                plans.name AS plan_name,
                plans.api_call_limit,
                plans.ai_token_limit
            FROM subscriptions
            JOIN plans ON subscriptions.plan_id = plans.id
            WHERE subscriptions.tenant_id = ?
            """,
            (tenant_id,),
        ).fetchone()

        if subscription is None or subscription["status"] != "active":
            connection.rollback()
            return {
                "error": "Subscription is not active",
                "status_code": 402,
            }

        if usage_type == "api_call":
            limit = subscription["api_call_limit"]
        elif usage_type == "ai_token":
            limit = subscription["ai_token_limit"]
        else:
            connection.rollback()
            return {
                "error": "Unsupported usage type",
                "status_code": 400,
            }

        # 3. Calculate this month's existing usage.
        current_usage = connection.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total
            FROM usage_events
            WHERE tenant_id = ?
              AND usage_type = ?
              AND strftime('%Y-%m', created_at)
                  = strftime('%Y-%m', 'now')
            """,
            (tenant_id, usage_type),
        ).fetchone()["total"]

        # Exact quota is allowed; only usage above it is rejected.
        if current_usage + quantity > limit:
            connection.rollback()
            return {
                "error": "Monthly usage quota exceeded",
                "status_code": 429,
                "used": current_usage,
                "requested": quantity,
                "limit": limit,
            }

        # 4. Record the billable usage exactly once.
        cursor = connection.execute(
            """
            INSERT INTO usage_events
                (tenant_id, usage_type, quantity, idempotency_key)
            VALUES (?, ?, ?, ?)
            """,
            (tenant_id, usage_type, quantity, idempotency_key),
        )

        event = connection.execute(
            """
            SELECT id, tenant_id, usage_type, quantity,
                   idempotency_key, created_at
            FROM usage_events
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

        connection.commit()

        return {
            "event": dict(event),
            "duplicate": False,
        }

    except sqlite3.IntegrityError:
        connection.rollback()
        raise

    finally:
        connection.close()