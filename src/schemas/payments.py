from datetime import datetime
from decimal import Decimal
from typing import Optional, cast

from pydantic import BaseModel, model_validator, Field

from database import StatusPayment

from schemas.examples.payments import (
    payment_example_schema,
    payments_history_example_schema,
)


class PaymentSchema(BaseModel):
    id: int
    created_at: datetime
    amount: Decimal
    status: StatusPayment

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [payment_example_schema]},
    }


class PaymentsHistorySchema(BaseModel):
    payments: list[PaymentSchema]

    model_config = {
        "json_schema_extra": {"examples": [payments_history_example_schema]},
    }


class AllUsersPaymentsSchema(PaymentsHistorySchema):
    prev_page: str
    next_page: str
    items: int


class PaymentsFilterParams(BaseModel):
    limit: int = Field(10, gt=0, le=100)
    offset: int = Field(0, ge=0)
    user_id: Optional[int] = Field(None, gt=0)
    date_from: Optional[datetime] = Field(None)
    date_to: Optional[datetime] = Field(None)
    status: Optional[StatusPayment] = Field(
        None,
    )

    @model_validator(mode="after")
    def check_date_range(self) -> "PaymentsFilterParams":
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValueError(
                    "`date_from` must be before or equal to `date_to`."
                )
        return self
