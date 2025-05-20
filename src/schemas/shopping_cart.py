from pydantic import BaseModel

from .movies import MovieBaseSchema


class CartItemSchema(BaseModel):
    id: int
    movie_id: int
    movie: MovieBaseSchema

    model_config = {
        "from_attributes": True
    }


class ResponseShoppingCartSchema(BaseModel):
    id: int
    user_id: int
    cart_items: list[CartItemSchema]
