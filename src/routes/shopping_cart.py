from http.client import HTTPException

from fastapi import APIRouter, Depends, Path, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from database.models.shopping_cart import PurchaseModel
from routes.utils import get_required_access_token_payload

from database import get_db, MovieModel, CartModel, CartItemModel
from schemas import (
    AccessTokenPayload,
    ResponseShoppingCartSchema,
    MessageResponseSchema
)

router = APIRouter()

@router.post(
    "/items/{movie_id}/",
    response_model=ResponseShoppingCartSchema,
    summary="Add movie to shopping cart",
    description=("Adding a movie to the shopping cart, with automatic "
                 "creation of a shopping cart if it does not exist yet."
                 ),
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with the given ID was not found."}
                }
            },
        },
        400: {
            "description": "Movie already purchased, already exists in shopping cart",
            "content": {
                "application/json": {
                    "example": {
                        "movie_not_found": {
                            "detail": "You already purchased this movie."
                        },
                        "user_not_found": {
                            "detail": "Movie already exists in shopping cart."
                        }
                    }

                }
            },
        },

    },
    status_code=200
)
async def add_movie_to_cart(
    movie_id: int = Path(..., ge=0),
    token_payload: AccessTokenPayload = Depends(
        get_required_access_token_payload
    ),
    db: AsyncSession = Depends(get_db),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with the ID provided does not exist."
        )
    user_id = token_payload["user_id"]

    stmt = select(PurchaseModel.id).where(
        (PurchaseModel.movie_id == movie_id) &
        (PurchaseModel.user_id == user_id)
    )
    result = await db.execute(stmt)
    purchase_id = result.scalars().first()
    if purchase_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already purchased this movie."
        )
    stmt = select(CartModel).where(CartModel.user_id == user_id)
    result = await db.execute(stmt)
    cart = result.scalars().first()
    if not cart:
        cart = CartModel(user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
    else:
        if movie_id in (item.movie_id for item in cart.cart_items):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Movie already exists in shopping cart."
            )

    item = CartItemModel(movie_id=movie_id, cart_id=cart.id)
    db.add(item)
    await db.commit()
    await db.refresh(cart, attribute_names=["cart_items"])
    return ResponseShoppingCartSchema.model_validate(cart, from_attributes=True)


@router.delete(
    "/items/{movie_id}/",
    response_model=ResponseShoppingCartSchema,
    summary="Remove movie from shopping cart",
    description=("Remove the movie from the cart according"
                 " to the movie ID provided."),
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie with the given ID was not found."}
                }
            },
        },
        400: {
            "description": "Movie not exists in shopping cart",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Movie not exists in shopping cart"
                    },
                }
            },
        },

    },
    status_code=200
)
async def remove_movie_from_cart(
    movie_id: int = Path(..., ge=0),
    token_payload: AccessTokenPayload = Depends(
        get_required_access_token_payload
    ),
    db: AsyncSession = Depends(get_db),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with the ID provided does not exist."
        )
    user_id = token_payload["user_id"]

    stmt = select(CartModel).where(CartModel.user_id == user_id)
    result = await db.execute(stmt)
    cart = result.scalars().first()
    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You do not have shopping cart yet."
        )
    for item in cart.cart_items:
        if item.movie_id == movie_id:
            await db.delete(item)
            await db.commit()
            await db.refresh(cart, attribute_names=["cart_items"])
            return ResponseShoppingCartSchema.model_validate(
                cart, from_attributes=True)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Movie not exists in shopping cart."
    )


@router.get(
    "/items/",
    response_model=ResponseShoppingCartSchema,
    summary="List movie in shopping cart",
    description="List movie in shopping cart",
    responses={
        404: {
            "description": "Shopping cart not exists",
            "content": {
                "application/json": {
                    "example": "You do not have shopping cart yet."
                }
            },
        },
    },
    status_code=200
)
async def list_items_in_cart(
    token_payload: AccessTokenPayload = Depends(
        get_required_access_token_payload
    ),
    db: AsyncSession = Depends(get_db),
):

    user_id = token_payload["user_id"]
    stmt = select(CartModel).where(CartModel.user_id == user_id)
    result = await db.execute(stmt)
    cart = result.scalars().first()
    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You do not have shopping cart yet."
        )
    return ResponseShoppingCartSchema.model_validate(
        cart, from_attributes=True)


@router.delete(
    "/items/",
    response_model=MessageResponseSchema,
    summary="Clear shopping cart",
    description="Remove all items from shopping cart.",
    responses={
        200: {
            "description": "Cart cleared successfully",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Shopping cart has been cleared successfully."
                    }
                },
            },
        },
        404: {
            "description": "Shopping cart not exists",
            "content": {
                "application/json": {
                    "example": "You do not have shopping cart yet."
                }
            },
        },

    },
    status_code=200
)
async def clear_shopping_cart(
    token_payload: AccessTokenPayload = Depends(
        get_required_access_token_payload
    ),
    db: AsyncSession = Depends(get_db),
):

    user_id = token_payload["user_id"]

    stmt = select(CartModel).where(CartModel.user_id == user_id)
    result = await db.execute(stmt)
    cart = result.scalars().first()
    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You do not have shopping cart yet."
        )
    await db.execute(
        delete(CartItemModel).where(CartItemModel.cart_id == cart.id)
    )
    await db.commit()
    return MessageResponseSchema(
        detail="Shopping cart has been cleared successfully."
    )

