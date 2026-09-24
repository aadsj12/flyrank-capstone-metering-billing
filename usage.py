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

        ai_tokens = connection.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total
            FROM usage_events
            WHERE tenant_id = ?
              AND usage_type = 'ai_token'
              AND strftime('%Y-%m', created_at)
                  = strftime('%Y-%m', 'now')
            """,
            (tenant_id,),
        ).fetchone()["total"]

        return {
            "tenant_id": tenant_id,
            "plan": subscription["plan_name"],
            "subscription_status": subscription["status"],
            "usage": {
                "api_calls": {
                    "used": api_calls,
                    "limit": subscription["api_call_limit"],
                    "remaining": max(
                        subscription["api_call_limit"] - api_calls, 0
                    ),
                },
                "ai_tokens": {
                    "used": ai_tokens,
                    "limit": subscription["ai_token_limit"],
                    "remaining": max(
                        subscription["ai_token_limit"] - ai_tokens, 0
                    ),
                },
            },
        }

    finally:
        connection.close()