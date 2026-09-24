import os
import sqlite3

import stripe
from dotenv import load_dotenv

from database import get_connection

load_dotenv()

WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


def construct_stripe_event(payload: bytes, signature: str):
    if not WEBHOOK_SECRET:
        raise ValueError("STRIPE_WEBHOOK_SECRET is not configured")

    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature,
        secret=WEBHOOK_SECRET,
    )


def _get_plan_id(connection, plan_name: str):
    plan = connection.execute(
        """
        SELECT id
        FROM plans
        WHERE name = ?
        """,
        (plan_name,),
    ).fetchone()

    if plan is None:
        raise ValueError(f"{plan_name} plan not found")

    return plan["id"]


def _sync_subscription_event(connection, subscription):
    tenant_id = subscription.get("metadata", {}).get("tenant_id")

    if not tenant_id:
        existing = connection.execute(
            """
            SELECT tenant_id
            FROM subscriptions
            WHERE stripe_subscription_id = ?
            """,
            (subscription.get("id"),),
        ).fetchone()

        if existing:
            tenant_id = existing["tenant_id"]

    if not tenant_id:
        return

    stripe_status = subscription.get("status", "unknown")

    active_statuses = {
        "active",
        "trialing",
    }

    if stripe_status in active_statuses:
        plan_id = _get_plan_id(connection, "Pro")
        local_status = "active"
    else:
        plan_id = _get_plan_id(connection, "Free")
        local_status = stripe_status

    connection.execute(
        """
        UPDATE subscriptions
        SET plan_id = ?,
            status = ?,
            stripe_customer_id = COALESCE(?, stripe_customer_id),
            stripe_subscription_id = COALESCE(
                ?,
                stripe_subscription_id
            ),
            updated_at = CURRENT_TIMESTAMP
        WHERE tenant_id = ?
        """,
        (
            plan_id,
            local_status,
            subscription.get("customer"),
            subscription.get("id"),
            int(tenant_id),
        ),
    )


def process_stripe_event(event):
    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        event_id = event["id"]
        event_type = event["type"]

        existing = connection.execute(
            """
            SELECT id
            FROM stripe_events
            WHERE stripe_event_id = ?
            """,
            (event_id,),
        ).fetchone()

        if existing:
            connection.commit()
            return {
                "processed": False,
                "duplicate": True,
            }

        event_object = event["data"]["object"].to_dict()

        if event_type == "checkout.session.completed":
            tenant_id = (
                event_object.get("metadata", {}).get("tenant_id")
                or event_object.get("client_reference_id")
            )

            if tenant_id:
                pro_plan_id = _get_plan_id(connection, "Pro")

                connection.execute(
                    """
                    UPDATE subscriptions
                    SET plan_id = ?,
                        status = 'active',
                        stripe_customer_id = ?,
                        stripe_subscription_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE tenant_id = ?
                    """,
                    (
                        pro_plan_id,
                        event_object.get("customer"),
                        event_object.get("subscription"),
                        int(tenant_id),
                    ),
                )

        elif event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            _sync_subscription_event(
                connection,
                event_object,
            )

        connection.execute(
            """
            INSERT INTO stripe_events (
                stripe_event_id,
                event_type
            )
            VALUES (?, ?)
            """,
            (event_id, event_type),
        )

        connection.commit()

        return {
            "processed": True,
            "duplicate": False,
            "event_type": event_type,
        }

    except (sqlite3.Error, ValueError):
        connection.rollback()
        raise

    finally:
        connection.close()