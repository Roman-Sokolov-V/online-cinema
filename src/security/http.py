from typing import Optional

from fastapi import Request, HTTPException, status, Header


def check_token(authorization) -> str:
    """
    Validate and extract the Bearer token from the Authorization header value.
    Args:
        authorization (str): The value of the Authorization header.
    Returns:
        str: The extracted token.
    Raises:
        HTTPException: If the header format is invalid (not Bearer or token missing).
    """
    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )
    return token


def get_auth_token(authorization: str = Header(...)) -> str:
    """
    Extracts the Bearer token from the Authorization header.

    :param authorization: authorization header value.
    :return: Extracted token string.
    :raises HTTPException:
            - 401 Unauthorized if the Authorization header is missing.
            - 401 Unauthorized if the header format is invalid.
    """
    return check_token(authorization)


def get_optional_auth_token(
        authorization: Optional[str] = Header(default=None)) -> None:
    """
    For swagger documentation only, for view not required authorization field
    :param authorization: authorization header value.
    """
    pass


def get_token(request: Request) -> str:
    """
    Extracts the Bearer token from request.

    :param request: request value.
    :return: Extracted token string.
    :raises HTTPException:
            - 401 Unauthorized if the Authorization header is missing.
            - 401 Unauthorized if the header format is invalid.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing"
        )
    return check_token(authorization)


def get_token_or_none(request: Request) -> str | None:
    """
    Extracts the Bearer token from the Authorization header.

    :param request: FastAPI Request object.
    :return: str | None: The extracted Bearer token, or None if the Authorization header is missing.
    :raises: - 401 Unauthorized if the Authorization header exists but has an invalid format.
    """
    authorization: str = request.headers.get("Authorization")

    if not authorization:
        return None
    return check_token(authorization)
