from fastapi import APIRouter, Request, Header, Depends, HTTPException, status
from fastapi.responses import Response, JSONResponse
import stripe

from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings, BaseAppSettings
from database import get_db
from routes.crud.orders import set_status_canceled
from routes.crud.payments import create_payment


router = APIRouter()


settings: BaseAppSettings = get_settings()

stripe.api_key = settings.STRIPE_SECRET_KEY
webhook_secret = settings.STRIPE_WEBHOOK_SECRET


@router.post(
    "/",
    summary="Webhook - order has paid",
    description="Endpoint to accept Webhook on successful payment and "
    "automatic creation of Payment, and replacement of Order "
    "status as 'successful'.",
    status_code=200,
)
async def webhook_received(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(get_db),
):

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=stripe_signature, secret=webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        return JSONResponse(
            status_code=400, content={"error": "Invalid signature"}
        )
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        try:
            await create_payment(
                db=db, session_id=event["data"]["object"]["id"]
            )
        except HTTPException as e:
            raise e
    elif event_type in {"checkout.session.expired", "payment_intent.canceled"}:
        await set_status_canceled(
            db=db, session_id=event["data"]["object"]["id"]
        )
    return Response(status_code=status.HTTP_200_OK)
