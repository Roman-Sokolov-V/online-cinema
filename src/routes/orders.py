from typing import Any, Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload

from routes.crud.orders import get_orders_stmt
from routes.utils import get_required_access_token_payload

from database import (
    get_db,
    MovieModel,
    CartModel,
    CartItemModel,
    OrderModel,
    OrderItemModel,
    StatusEnum, UserModel, UserGroupModel
)
from schemas import (
    AccessTokenPayload,
    CreateOrderSchema
)
from schemas.orders import ResponseListOrdersSchema, FilterParams, OrderSchema

router = APIRouter()


@router.post(
    "/place/",
    response_model=CreateOrderSchema,
    summary="Create order",
    description="User place order for movies in their cart",
    responses={
        404: {
            "description": "The user dose not have cart yet",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Cart not found."}
                }
            },
        },
        400: {
            "description": "User don't have any items in cart. or IntegrityError",
            "content": {
                "application/json": {
                    "example": {
                        "cart is empty": {
                            "detail": "You don't have any items in cart."
                        },
                        "IntegrityError": {
                            "detail": "Integrity error: {str(e.orig)"
                        }
                    }

                }
            },
        },

    },
    status_code=201
)
async def place_order(
        token_payload: AccessTokenPayload = Depends(
            get_required_access_token_payload
        ),
        db: AsyncSession = Depends(get_db),
):
    user_id = token_payload["user_id"]
    stmt: Any = select(CartModel).where(CartModel.user_id == user_id)
    result = await db.execute(stmt)
    cart: CartModel | None = result.scalars().first()
    if cart is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found."
        )
    if not cart.cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You don't have any items in cart."
        )
    movies_in_cart: list[MovieModel] = [item.movie for item in cart.cart_items]
    movies_id_in_cart = [movie.id for movie in movies_in_cart]

    stmt = (
        select(OrderItemModel.movie_id)
        .join(OrderModel, OrderModel.id == OrderItemModel.order_id)
        .where(
            (OrderModel.status == StatusEnum.PENDING) &
            (OrderModel.user_id == user_id) &
            (OrderItemModel.movie_id.in_(movies_id_in_cart))
        )
    )
    result = await db.execute(stmt)
    movie_ids_in_other_orders = result.scalars().all()

    movies_for_ordering = [
        movie
        for movie
        in movies_in_cart
        if movie.id not in movie_ids_in_other_orders
    ]
    total_amount = sum(movie.price for movie in movies_for_ordering)

    try:
        order = OrderModel(user_id=user_id, total_amount=total_amount)
        db.add(order)
        await db.flush()
        for movie in movies_for_ordering:
            order_item = OrderItemModel(
                order_id=order.id,
                movie_id=movie.id,
                price_at_order=movie.price
            )
            db.add(order_item)
        await db.execute(
            delete(CartItemModel).where(CartItemModel.cart_id == cart.id))
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Integrity error: {getattr(e, 'orig', str(e))}"
        )
    message = f"Movies from the cart added to the order successfully."
    messages = [message]
    if movie_ids_in_other_orders:
        messages.append(
            f"Movies with the following IDs: {movie_ids_in_other_orders} have "
            f"not been added to the order because they are already in your "
            f"other orders awaiting payment."
        )
    titles = [movie.name for movie in movies_for_ordering]
    await db.refresh(order)
    response = CreateOrderSchema(
        id=order.id,
        created_at=order.created_at,
        movies=titles,
        total_amount=order.total_amount,
        status=order.status,
        detail=" ".join(messages)
    )
    return response


@router.get(
    "/list/",
    response_model=ResponseListOrdersSchema,
    summary="List orders",
    description=(
            "This endpoint can be used by both regular users and admins. "
            "If a regular user provides the 'user_id' query parameter, it will"
            " be automatically overridden with the ID of the authenticated"
            " user."
    ),
    status_code=200
)
async def list_orders(
        filtered_query: Annotated[FilterParams, Query()],
        token_payload: AccessTokenPayload = Depends(
            get_required_access_token_payload
        ),
        db: AsyncSession = Depends(get_db),
) -> ResponseListOrdersSchema:
    request_user_id = token_payload["user_id"]
    stmt = (
        select(UserGroupModel.name)
        .join(UserModel.group)
        .where(UserModel.id == request_user_id)
    )
    result = await db.execute(stmt)
    request_user_group_name = result.scalars().first()
    if request_user_group_name != "admin":
        # Ігноруємо user_id з query для звичайного користувача,
        # використовуємо значення з токена
        filtered_query.user_id = request_user_id
    stmt_orders = get_orders_stmt(filtered_query)
    result_orders = await db.execute(stmt_orders)
    orders = result_orders.scalars().all()
    response = ResponseListOrdersSchema(
        orders=[
            OrderSchema(
                id=order.id,
                created_at=order.created_at,
                movies=[item.movie.name for item in order.order_items],
                total_amount=order.total_amount,
                status=order.status
            )
            for order in orders
        ],
    )

    return response



    # stmt = select(CartModel).where(CartModel.user_id == user_id)
    # result = await db.execute(stmt)
    # cart = result.scalars().first()
    # if not cart:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail=f"You do not have shopping cart yet."
    #     )
    # return ResponseShoppingCartSchema.model_validate(
    #     cart, from_attributes=True)

# @router.delete(
#     "/items/",
#     response_model=MessageResponseSchema,
#     summary="Clear shopping cart",
#     description="Remove all items from shopping cart.",
#     responses={
#         200: {
#             "description": "Cart cleared successfully",
#             "content": {
#                 "application/json": {
#                     "example": {
#                         "detail": "Shopping cart has been cleared successfully."
#                     }
#                 },
#             },
#         },
#         404: {
#             "description": "Shopping cart not exists",
#             "content": {
#                 "application/json": {
#                     "example": "You do not have shopping cart yet."
#                 }
#             },
#         },
#
#     },
#     status_code=200
# )
# async def clear_shopping_cart(
#         token_payload: AccessTokenPayload = Depends(
#             get_required_access_token_payload
#         ),
#         db: AsyncSession = Depends(get_db),
# ):
#     user_id = token_payload["user_id"]
#
#     stmt = select(CartModel).where(CartModel.user_id == user_id)
#     result = await db.execute(stmt)
#     cart = result.scalars().first()
#     if not cart:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"You do not have shopping cart yet."
#         )
#     await db.execute(
#         delete(CartItemModel).where(CartItemModel.cart_id == cart.id)
#     )
#     await db.commit()
#     return MessageResponseSchema(
#         detail="Shopping cart has been cleared successfully."
#     )
#
#
# @router.delete(
#     "/items/{movie_id}/",
#     response_model=ResponseShoppingCartSchema,
#     summary="Remove movie from shopping cart",
#     description=("Remove the movie from the cart according"
#                  " to the movie ID provided."),
#     responses={
#         404: {
#             "description": "Movie not found.",
#             "content": {
#                 "application/json": {
#                     "example": {
#                         "detail": "Movie with the given ID was not found."}
#                 }
#             },
#         },
#         400: {
#             "description": "Movie not exists in shopping cart",
#             "content": {
#                 "application/json": {
#                     "example": {
#                         "detail": "Movie not exists in shopping cart"
#                     },
#                 }
#             },
#         },
#
#     },
#     status_code=200
# )
# async def remove_movie_from_cart(
#         movie_id: int = Path(..., ge=0),
#         token_payload: AccessTokenPayload = Depends(
#             get_required_access_token_payload
#         ),
#         db: AsyncSession = Depends(get_db),
# ):
#     movie = await db.get(MovieModel, movie_id)
#     if not movie:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"Movie with the ID provided does not exist."
#         )
#     user_id = token_payload["user_id"]
#
#     stmt = select(CartModel).where(CartModel.user_id == user_id)
#     result = await db.execute(stmt)
#     cart = result.scalars().first()
#     if not cart:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"You do not have shopping cart yet."
#         )
#     for item in cart.cart_items:
#         if item.movie_id == movie_id:
#             await db.delete(item)
#             await db.commit()
#             await db.refresh(cart, attribute_names=["cart_items"])
#             return ResponseShoppingCartSchema.model_validate(
#                 cart, from_attributes=True)
#     raise HTTPException(
#         status_code=status.HTTP_400_BAD_REQUEST,
#         detail=f"Movie not exists in shopping cart."
#     )
#
#
# @router.get(
#     "/{user_id}/",
#     response_model=ResponseShoppingCartSchema,
#     dependencies=[Depends(is_admin)],
#     summary="Retrieve users shopping cart",
#     description=("<h3>For admins only</h3>"
#                  "<p>Retrieve users shopping cart, by user_id.</p>"),
#     responses={
#         404: {
#             "description": "Shopping cart not exists",
#             "content": {
#                 "application/json": {
#                     "example": "User do not have shopping cart yet."
#                 }
#             },
#         },
#     },
#     status_code=200
# )
# async def retrieve_users_cart(
#         user_id: int = Path(..., ge=0),
#         db: AsyncSession = Depends(get_db),
# ):
#     stmt = select(CartModel).where(CartModel.user_id == user_id)
#     result = await db.execute(stmt)
#     cart = result.scalars().first()
#     if not cart:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"You do not have shopping cart yet."
#         )
#     return ResponseShoppingCartSchema.model_validate(
#         cart, from_attributes=True)
