from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel

from database import StatusEnum, MovieModel
from schemas.examples.orders import create_order_example_schema



class OrderSchema(BaseModel):
    id: int
    created_at: datetime
    movies: list[str]
    total_amount: Decimal
    status: StatusEnum


class CreateOrderSchema(OrderSchema):
    detail: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                create_order_example_schema,
            ]
        }
    }
