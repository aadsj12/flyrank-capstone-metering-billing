from database import get_connection


def check_quota(tenant_id: int, usage_type: str, requested_quantity: int):
    connection = get_connection()

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

    if subscription is None:
        connection.close()
        return {
            "allowed": False,
            "status_code": 402,
            "message": "No active subscription found",
        }

    if subscription["status"] != "active":
        connection.close()
        return {
            "allowed": False,
            "status_code": 402,
            "message": "Subscription is not active",
        }

    if usage_type == "api_call":
        limit = subscription["api_call_limit"]
    elif usage_type == "ai_token":
        limit = subscription["ai_token_limit"]
    else:
        connection.close()
        raise ValueError("Unsupported usage type")

    current_usage = connection.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) AS total
        FROM usage_events
        WHERE tenant_id = ?
          AND usage_type = ?
          AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
        """,
        (tenant_id, usage_type),
    ).fetchone()["total"]

    connection.close()

    projected_usage = current_usage + requested_quantity

    if projected_usage > limit:
        return {
            "allowed": False,
            "status_code": 429,
            "message": "Monthly usage quota exceeded",
            "used": current_usage,
            "requested": requested_quantity,
            "limit": limit,
        }

    return {
        "allowed": True,
        "used": current_usage,
        "requested": requested_quantity,
        "projected": projected_usage,
        "limit": limit,
        "plan": subscription["plan_name"],
    }
