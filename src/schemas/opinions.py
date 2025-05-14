from pydantic import BaseModel

from schemas.examples.opinions import (
    response_commentary_schema_example,
    response_reply_schema_example,
)


class CommentSchema(BaseModel):
    content: str


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


class ReplySchema(CommentSchema):
    pass


class ResponseReplySchema(ResponseCommentarySchema):
    parent_id: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                response_reply_schema_example
            ]
        }
    }