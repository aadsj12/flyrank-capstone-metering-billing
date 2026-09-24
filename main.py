from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from metering import record_usage
from usage import get_usage_summary
from stripe_service import create_checkout_session
import stripe

from stripe_webhook import construct_stripe_event, process_stripe_event


app = FastAPI(title="Usage Metering & Billing Engine")


class GenerateRequest(BaseModel):
    tenant_id: int = Field(gt=0)
    usage_type: str
    quantity: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
def generate(request: GenerateRequest):
    result = record_usage(
        tenant_id=request.tenant_id,
        usage_type=request.usage_type,
        quantity=request.quantity,
        idempotency_key=request.idempotency_key,
    )

    if "error" in result:
        raise HTTPException(
            status_code=result["status_code"],
            detail={
                key: value
                for key, value in result.items()
                if key != "status_code"
            },
        )

    return result

@app.get("/usage")
def usage(tenant_id: int):
    summary = get_usage_summary(tenant_id)

    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="Tenant subscription not found",
        )

    return summary

@app.post("/checkout")
def checkout(tenant_id: int):
    try:
        return create_checkout_session(tenant_id)
    except ValueError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    if not signature:
        raise HTTPException(
            status_code=400,
            detail="Missing Stripe signature",
        )

    try:
        event = construct_stripe_event(payload, signature)

    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(
            status_code=400,
            detail="Invalid Stripe webhook signature",
        )

    try:
        result = process_stripe_event(event)
        return result

    except Exception as error:
        print("WEBHOOK ERROR:", repr(error))
        raise HTTPException(
            status_code=500,
            detail="Webhook processing failed",
        )