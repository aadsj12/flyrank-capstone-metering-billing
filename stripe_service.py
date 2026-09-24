import os

import stripe
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID")


def create_checkout_session(tenant_id: int):
    if not stripe.api_key:
        raise ValueError("STRIPE_SECRET_KEY is not configured")

    if not STRIPE_PRO_PRICE_ID:
        raise ValueError("STRIPE_PRO_PRICE_ID is not configured")

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[
            {
                "price": STRIPE_PRO_PRICE_ID,
                "quantity": 1,
            }
        ],
        success_url="http://127.0.0.1:8000/usage?tenant_id={}".format(
        tenant_id
    ),
    cancel_url="http://127.0.0.1:8000/usage?tenant_id={}".format(
        tenant_id
    ),
        client_reference_id=str(tenant_id),
        metadata={
            "tenant_id": str(tenant_id),
        },
        subscription_data={
            "metadata": {
                "tenant_id": str(tenant_id),
            }
        },
    )

    return {
        "checkout_session_id": session.id,
        "checkout_url": session.url,
    }
