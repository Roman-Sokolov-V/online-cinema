from typing import Optional

from pydantic import BaseModel, model_validator, Field

from schemas.examples.opinions import (
    response_commentary_schema_example,
    response_reply_schema_example, comment_schema_example,
    reply_schema_example,
)


class CommentSchema(BaseModel):
    content: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                comment_schema_example
            ]
        }
    }


class ResponseCommentarySchema(BaseModel):
    id: int
    content: str
    movie_id: int
    user_id: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                response_commentary_schema_example
            ]
        }
    }


class ReplySchema(BaseModel):
    content: Optional[str] = None
    is_like: Optional[bool] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                reply_schema_example
            ]
        }
    }

    @model_validator(mode="after")
    def check_reaction_needed(self) -> "ReplySchema":
        if self.content is None and self.is_like is None:
            raise ValueError("At least one of content or is_like must be set")
        return self


class ResponseReplySchema(BaseModel):
    id: int
    content: str | None
    is_like: bool | None
    movie_id: int
    user_id: int
    parent_id: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                response_reply_schema_example
            ]
        }
    }


class RateSchema(BaseModel):
    rate: int = Field(..., ge=0, lt=10)


