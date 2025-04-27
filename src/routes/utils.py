# from sqlalchemy import select
# from fastapi import status, HTTPException
#
# from database import UserGroupModel, UserModel, UserGroupEnum, UserProfileModel
# from exceptions import InvalidTokenError, TokenExpiredError, BaseSecurityError
#
#
# def check_access_token(authorization, jwt_manager) -> dict:
#     try:
#         token_type, token = authorization.split()
#         # If authorization.split() does not contain exactly two elements, a ValueError will be raised.
#         if token_type != "Bearer":
#             raise ValueError("Invalid token type")
#         token_dict = jwt_manager.decode_access_token(token)
#     except (InvalidTokenError, TokenExpiredError, ValueError):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token"
#         )
#     return token_dict
#
#
# async def get_user_profile_check_permissions(token, jwt_manager, user_id, db):
#     try:
#         payload = jwt_manager.decode_access_token(token)
#         token_user_id = payload.get("user_id")
#     except BaseSecurityError as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=str(e)
#         )
#
#     if user_id != token_user_id:
#         stmt = (
#             select(UserGroupModel)
#             .join(UserModel)
#             .where(UserModel.id == token_user_id)
#         )
#         result = await db.execute(stmt)
#         user_group = result.scalars().first()
#         if not user_group or user_group.name == UserGroupEnum.USER:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="You don't have permission to edit this profile."
#             )
#         stmt = select(UserModel).where(UserModel.id == user_id)
#         result = await db.execute(stmt)
#         user = result.scalars().first()
#         if not user or not user.is_active:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="User not found or not active."
#             )
#         stmt_profile = select(UserProfileModel).where(
#             UserProfileModel.user_id == user.id)
#         result_profile = await db.execute(stmt_profile)
#         existing_profile = result_profile.scalars().first()
#         return existing_profile

from config import get_jwt_auth_manager
from exceptions import InvalidTokenError, TokenExpiredError
from schemas import AccessTokenPayload
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface

from fastapi import Depends, status, HTTPException


def get_access_token_payload(
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
) -> AccessTokenPayload:
    try:
        token_payload = jwt_manager.decode_access_token(token)
    except (InvalidTokenError, TokenExpiredError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return token_payload
