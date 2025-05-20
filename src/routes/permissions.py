from fastapi import Depends, status, HTTPException

from routes.utils import get_required_access_token_payload
from schemas import AccessTokenPayload


def is_any_group(
        payload: AccessTokenPayload = Depends(get_required_access_token_payload)
) -> AccessTokenPayload:
    """
    Access to the basic user interface
    """
    return payload


def is_moderator_or_admin_group(
        payload: AccessTokenPayload = Depends(get_required_access_token_payload)
) -> AccessTokenPayload:
    """
    In addition to catalog and user interface access, can manage movies
    on the site through the admin panel, view sales, etc.
    """
    if payload["group"] not in ["moderator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not moderator or admin."
        )
    return payload


def is_admin(
        payload: AccessTokenPayload = Depends(get_required_access_token_payload)
) -> AccessTokenPayload:
    """
    In addition to catalog and user interface access, can manage movies
    on the site through the admin panel, view sales, etc.
    """
    if payload["group"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not admin."
        )
    return payload


def is_owner_or_admin(
        user_id: int,
        payload: AccessTokenPayload = Depends(get_required_access_token_payload),

):
    if payload["user_id"] != user_id and payload["group"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied, not enough permissions"
        )


def is_moderator_or_admin(
        payload: AccessTokenPayload = Depends(get_required_access_token_payload)
) -> AccessTokenPayload:
    """
    In addition to catalog and user interface access, can manage movies
    on the site through the admin panel, view sales, etc.
    """
    if payload["group"] not in ["admin", "moderator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not admin."
        )
    return payload

