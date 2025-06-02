from datetime import datetime
from decimal import Decimal
from typing import Optional, cast

from pydantic import BaseModel, model_validator, Field

from database import StatusPayment

from schemas.examples.payments import (
    payment_example_schema,
    payments_history_example_schema
)


class PaymentSchema(BaseModel):
    id: int
    created_at: datetime
    amount: Decimal
    status: StatusPayment

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                payment_example_schema
            ]
        },
    }


class PaymentsHistorySchema(BaseModel):
    payments: list[PaymentSchema]

    model_config = {
        "json_schema_extra": {
            "examples": [
                payments_history_example_schema
            ]
        },
    }
