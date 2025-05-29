from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from database import OrderStatus
from schemas.examples.orders import (
    create_order_example_schema,
    response_list_orders_example_schema
)


class OrderSchema(BaseModel):
    id: int
    created_at: datetime
    total_amount: Decimal
    status: OrderStatus
    movies: list[str]


class CreateOrderSchema(OrderSchema):
    detail: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                create_order_example_schema,
            ]
        }
    }


class ResponseListOrdersSchema(BaseModel):
    orders: list[OrderSchema]

    model_config = {
        "json_schema_extra": {
            "examples": [
                response_list_orders_example_schema,
            ]
        }
    }


class FilterParams(BaseModel):
    limit: int = Field(10, gt=0, le=100)
    offset: int = Field(0, ge=0)
    user_id: Optional[int] = Field(None, gt=0)
    date_from: Optional[datetime] = Field(None)
    date_to: Optional[datetime] = Field(None)
    status: Optional[OrderStatus] = Field(
        None,
        description="Order status: pending, paid, or canceled",
    )

    @model_validator(mode="after")
    def check_date_range(self) -> "FilterParams":
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValueError(
                    "`date_from` must be before or equal to `date_to`.")
        return self
