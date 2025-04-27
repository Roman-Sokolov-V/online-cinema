from typing import TypedDict


class AccessTokenPayload(TypedDict):
    user_id: int
    group: str
