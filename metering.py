import sqlite3

from database import get_connection
from pricing import calculate_token_cost


def record_usage(
    tenant_id: int,
    usage_type: str,
    quantity: int,
    idempotency_key: str,
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
):
    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        existing_event = connection.execute(
            """
            SELECT *
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

            quantity = (
                input_tokens
                + cached_input_tokens
                + output_tokens
                + reasoning_tokens
            )

            if quantity <= 0:
                connection.rollback()
                return {
                    "error": "AI token usage must be greater than zero",
                    "status_code": 400,
                }

        else:
            connection.rollback()
            return {
                "error": "Unsupported usage type",
                "status_code": 400,
            }

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

        if current_usage + quantity > limit:
            connection.rollback()
            return {
                "error": "Monthly usage quota exceeded",
                "status_code": 429,
                "used": current_usage,
                "requested": quantity,
                "limit": limit,
            }

        cost_microdollars = 0

        if usage_type == "ai_token":
            cost = calculate_token_cost(
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
                reasoning_tokens=reasoning_tokens,
            )
            cost_microdollars = cost["total_cost"]

        cursor = connection.execute(
            """
            INSERT INTO usage_events (
                tenant_id,
                usage_type,
                quantity,
                idempotency_key,
                input_tokens,
                cached_input_tokens,
                output_tokens,
                reasoning_tokens,
                cost_microdollars
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                usage_type,
                quantity,
                idempotency_key,
                input_tokens,
                cached_input_tokens,
                output_tokens,
                reasoning_tokens,
                cost_microdollars,
            ),
        )

        event = connection.execute(
            """
            SELECT *
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