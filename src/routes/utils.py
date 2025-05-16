from config import get_jwt_auth_manager
from exceptions import InvalidTokenError, TokenExpiredError
from schemas import AccessTokenPayload
from security.http import get_token, get_auth_token, get_optional_auth_token
from security.interfaces import JWTAuthManagerInterface

from fastapi import Depends, status, HTTPException


def get_access_token_payload(
        token: str = Depends(get_auth_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
) -> AccessTokenPayload:
    try:
        token_payload = jwt_manager.decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    return token_payload


def get_optional_access_token_payload(
        token: str = Depends(get_optional_auth_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
) -> AccessTokenPayload:
    return get_access_token_payload(token=token, jwt_manager=jwt_manager)


def get_required_access_token_payload(
        token: str = Depends(get_auth_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
) -> AccessTokenPayload:
    return get_access_token_payload(token=token, jwt_manager=jwt_manager)