from database import get_connection


def get_usage_summary(tenant_id: int):
    connection = get_connection()

    try:
        subscription = connection.execute(
            """
            SELECT
                plans.name AS plan_name,
                plans.api_call_limit,
                plans.ai_token_limit,
                subscriptions.status
            FROM subscriptions
            JOIN plans ON subscriptions.plan_id = plans.id
            WHERE subscriptions.tenant_id = ?
            """,
            (tenant_id,),
        ).fetchone()

        if subscription is None:
            return None

        api_calls = connection.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total
            FROM usage_events
            WHERE tenant_id = ?
              AND usage_type = 'api_call'
              AND strftime('%Y-%m', created_at)
                  = strftime('%Y-%m', 'now')
            """,
            (tenant_id,),
        ).fetchone()["total"]

        token_usage = connection.execute(
            """
            SELECT
                COALESCE(SUM(quantity), 0) AS total_tokens,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(cached_input_tokens), 0)
                    AS cached_input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(reasoning_tokens), 0)
                    AS reasoning_tokens,
                COALESCE(SUM(cost_microdollars), 0)
                    AS cost_microdollars
            FROM usage_events
            WHERE tenant_id = ?
              AND usage_type = 'ai_token'
              AND strftime('%Y-%m', created_at)
                  = strftime('%Y-%m', 'now')
            """,
            (tenant_id,),
        ).fetchone()

        ai_tokens = token_usage["total_tokens"]

        return {
            "tenant_id": tenant_id,
            "plan": subscription["plan_name"],
            "subscription_status": subscription["status"],
            "usage": {
                "api_calls": {
                    "used": api_calls,
                    "limit": subscription["api_call_limit"],
                    "remaining": max(
                        subscription["api_call_limit"] - api_calls,
                        0,
                    ),
                },
                "ai_tokens": {
                    "used": ai_tokens,
                    "limit": subscription["ai_token_limit"],
                    "remaining": max(
                        subscription["ai_token_limit"] - ai_tokens,
                        0,
                    ),
                    "breakdown": {
                        "input_tokens": token_usage["input_tokens"],
                        "cached_input_tokens":
                            token_usage["cached_input_tokens"],
                        "output_tokens": token_usage["output_tokens"],
                        "reasoning_tokens":
                            token_usage["reasoning_tokens"],
                    },
                },
            },
            "cost": {
                "currency": "USD",
                "unit": "microdollars",
                "monthly_total": token_usage["cost_microdollars"],
            },
        }

    finally:
        connection.close()