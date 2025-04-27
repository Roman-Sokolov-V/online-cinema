from fastapi import Depends, status, HTTPException

from routes.utils import get_access_token_payload
from schemas import AccessTokenPayload


def is_admin_group(
        payload: AccessTokenPayload = Depends(get_access_token_payload)
) -> AccessTokenPayload:
    if payload["group"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not admin."
        )
    return payload


def is_any_group(
        payload: AccessTokenPayload = Depends(get_access_token_payload)
) -> AccessTokenPayload:
    return payload
