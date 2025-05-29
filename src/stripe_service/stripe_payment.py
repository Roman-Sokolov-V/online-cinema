from decimal import Decimal
from typing import Any
from fastapi import HTTPException
import stripe
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_settings
from database import OrderModel

settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_session(
    total_amount: Decimal, titles: str, message: str
) -> stripe.checkout.Session:
    """
    Creates stripe payment session to pay
    """

    print("start create session")
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "order",
                        "description": titles,
                    },
                    "unit_amount": int(total_amount * 100),
                },
                "quantity": 1,
            }

        ],
        custom_text={
        "submit": {"message": message},
        },
        mode="payment",
        success_url=settings.PAYMENT_SUCCESS_URL,
        cancel_url=settings.PAYMENT_CANCEL_URL,
    )
    return checkout_session




# async def cancel_payment_intent(order_id: int, db: AsyncSession):
#     # Отримуємо session_id з БД
#     stmt = select(OrderModel.session_id).where(OrderModel.id == order_id)
#     result = await db.execute(stmt)
#     session_id = result.scalar_one_or_none()
#
#     if not session_id:
#         raise HTTPException(
#             status_code=404,
#             detail="Stripe session_id not found for this order",
#         )
#
#     try:
#         session = stripe.checkout.Session.retrieve(session_id)
#         payment_intent_id = session.payment_intent
#     except Exception as e:
#         raise HTTPException(
#             status_code=400, detail=f"Failed to retrieve Stripe session: {e}"
#         )
#
#     if not payment_intent_id:
#         raise HTTPException(
#             status_code=404,
#             detail="Payment intent not found for this session",
#         )
#
#     try:
#         payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
#     except Exception as e:
#         raise HTTPException(
#             status_code=400, detail=f"Failed to retrieve payment intent: {e}"
#         )
#
#     if payment_intent.status in {
#         "requires_payment_method",
#         "requires_capture",
#         "requires_confirmation",
#         "requires_action",
#     }:
#         try:
#             canceled_intent = stripe.PaymentIntent.cancel(payment_intent_id)
#             return canceled_intent
#         except Exception as e:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Error cancelling payment intent: {e}",
#             )
#
#     return {"status": payment_intent.status}
