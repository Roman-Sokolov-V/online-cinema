import asyncio
from decimal import Decimal
from typing import Any, Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload

from routes.crud.orders import get_orders_stmt, set_status_canceled
from routes.utils import get_required_access_token_payload

from database import (
    get_db,
    MovieModel,
    CartModel,
    CartItemModel,
    OrderModel,
    OrderItemModel,
    OrderStatus,
    UserModel,
    UserGroupModel,
)
from schemas import AccessTokenPayload, MessageResponseSchema
from schemas.orders import (
    ResponseListOrdersSchema,
    OrdersFilterParams,
    OrderSchema,
)
from stripe_service.stripe_payment import create_stripe_session

router = APIRouter()


@router.post(
    "/place/",
    summary="Create order",
    description="User place order for movies in their cart, srtipe session is "
    "created. Response redirect to payment page",
    responses={
        404: {
            "description": "The user dose not have cart yet",
            "content": {
                "application/json": {"example": {"detail": "Cart not found."}}
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
                            "detail": "Integrity error: some error"
                        },
                    }
                }
            },
        },
    },
    status_code=303,
)
async def place_order(
    token_payload: AccessTokenPayload = Depends(
        get_required_access_token_payload
    ),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    user_id = token_payload["user_id"]
    stmt: Any = select(CartModel).where(CartModel.user_id == user_id)
    result = await db.execute(stmt)
    cart: CartModel | None = result.scalars().first()
    if cart is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found."
        )
    if not cart.cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You don't have any items in cart.",
        )
    movies_in_cart: list[MovieModel] = [item.movie for item in cart.cart_items]
    movies_id_in_cart = [movie.id for movie in movies_in_cart]

    stmt = (
        select(OrderItemModel)
        .join(OrderModel, OrderModel.id == OrderItemModel.order_id)
        .where(
            (OrderModel.status == OrderStatus.PENDING)
            & (OrderModel.user_id == user_id)
            & (OrderItemModel.movie_id.in_(movies_id_in_cart))
        )
        .options(joinedload(OrderItemModel.movie))
    )
    result = await db.execute(stmt)
    items_in_other_orders = result.scalars().all()
    movie_in_other_orders = [item.movie for item in items_in_other_orders]
    movie_titles_in_other_orders = [
        movie.name for movie in movie_in_other_orders
    ]

    movies_for_ordering = [
        movie for movie in movies_in_cart if movie not in movie_in_other_orders
    ]
    total_amount = sum(
        (movie.price for movie in movies_for_ordering), Decimal("0")
    )

    if movie_titles_in_other_orders:
        message = (
            f"WARNING! Movies: {" ,".join(movie_titles_in_other_orders)} have "
            f"not been added to the order because they are already in your "
            f"other orders awaiting payment."
        )
    else:
        message = "Thank you for your purchase."

    titles = ", ".join([movie.name for movie in movies_for_ordering])

    try:
        order = OrderModel(user_id=user_id, total_amount=total_amount)
        db.add(order)
        await db.flush()
        checkout_session = await asyncio.create_task(
            asyncio.to_thread(
                create_stripe_session,
                total_amount=total_amount,
                titles=titles,
                message=message,
                order_id=order.id,
            )
        )
        session_id = checkout_session.id
        order.session_id = session_id

        for movie in movies_for_ordering:
            order_item = OrderItemModel(
                order=order, movie_id=movie.id, price_at_order=movie.price
            )
            db.add(order_item)
        await db.execute(
            delete(CartItemModel).where(CartItemModel.cart_id == cart.id)
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Integrity error: {getattr(e, 'orig', str(e))}",
        )

    return RedirectResponse(
        checkout_session.url, status_code=status.HTTP_303_SEE_OTHER  # type: ignore
    )


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
    status_code=200,
)
async def list_orders(
    filtered_query: Annotated[OrdersFilterParams, Query()],
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
                status=order.status,
            )
            for order in orders
        ],
    )
    return response


@router.patch(
    "/cancel/{order_id}/",
    response_model=MessageResponseSchema,
    summary="Cancel order",
    description="User cancel order by order_id, before payment is completed",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {"detail": "Order has canceled successfully."}
                }
            },
        },
        404: {
            "description": "There is no couple with user_id and order_id",
            "content": {
                "application/json": {
                    "example": {"detail": "Order not found in your orders"}
                }
            },
        },
        400: {
            "description": "Order already paid",
            "content": {
                "application/json": {
                    "example": {"detail": "Order already paid"}
                }
            },
        },
        409: {
            "description": "Order already cancelled",
            "content": {
                "application/json": {
                    "example": {"detail": "Order already cancelled"}
                }
            },
        },
    },
    status_code=200,
)
async def cancel_order(
    order_id: int = Path(..., gt=0),
    token_payload: AccessTokenPayload = Depends(
        get_required_access_token_payload
    ),
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    user_id = token_payload["user_id"]
    stmt = select(OrderModel).where(
        (OrderModel.user_id == user_id) & (OrderModel.id == order_id)
    )
    result = await db.execute(stmt)
    order = result.scalars().first()
    await set_status_canceled(order=order, db=db)
    return MessageResponseSchema(detail="Order has canceled successfully.")
