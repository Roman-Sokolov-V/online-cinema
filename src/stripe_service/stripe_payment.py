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
    total_amount: Decimal, titles: str, message: str, order_id: int
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
        success_url=(settings.PAYMENT_SUCCESS_URL + f"{order_id}/"),
        cancel_url=(settings.PAYMENT_CANCEL_URL + f"{order_id}/"),
    )
    return checkout_session
