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


def process_stripe_event(event):
    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        event_id = event["id"]
        event_type = event["type"]

        # Stripe may deliver the same webhook more than once.
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

        if event_type == "checkout.session.completed":
            session = event["data"]["object"].to_dict()

            tenant_id = session.get("metadata", {}).get("tenant_id")

            if not tenant_id:
                tenant_id = session.get("client_reference_id")

            if tenant_id:
                pro_plan = connection.execute(
                    """
                    SELECT id
                    FROM plans
                    WHERE name = 'Pro'
                    """
                ).fetchone()

                if pro_plan is None:
                    raise ValueError("Pro plan not found")

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
                        pro_plan["id"],
                        session.get("customer"),
                        session.get("subscription"),
                        int(tenant_id),
                    ),
                )

        connection.execute(
            """
            INSERT INTO stripe_events
                (stripe_event_id, event_type)
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
