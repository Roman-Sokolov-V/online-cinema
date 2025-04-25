from fastapi import status, HTTPException

from exceptions import InvalidTokenError, TokenExpiredError


def check_access_token(authorization, jwt_manager) -> dict:
    try:
        token_type, token = authorization.split()
        # If authorization.split() does not contain exactly two elements, a ValueError will be raised.
        if token_type != "Bearer":
            raise ValueError("Invalid token type")
        token_dict = jwt_manager.decode_access_token(token)
    except (InvalidTokenError, TokenExpiredError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return token_dict