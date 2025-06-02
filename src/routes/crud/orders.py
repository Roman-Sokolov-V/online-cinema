from fastapi  import HTTPException, status


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import Select
from sqlalchemy.orm import selectinload
from database import OrderModel, OrderStatus, OrderItemModel
from schemas import OrdersFilterParams


def get_orders_stmt(
        filtered_query: OrdersFilterParams
) -> Select:
    stmt = select(OrderModel)
    if filtered_query.user_id is not None:
        stmt = stmt.where(OrderModel.user_id == filtered_query.user_id)
    if filtered_query.date_from is not None:
        stmt = stmt.where(OrderModel.created_at >= filtered_query.date_from)
    if filtered_query.date_to is not None:
        stmt = stmt.where(OrderModel.created_at <= filtered_query.date_to)
    if filtered_query.status is not None:
        stmt = stmt.where(OrderModel.status == filtered_query.status)
    if filtered_query.offset is not None:
        stmt = stmt.offset(filtered_query.offset)
    if filtered_query.limit is not None:
        stmt = stmt.limit(filtered_query.limit)
    return stmt.options(
        selectinload(OrderModel.order_items)
        .selectinload(OrderItemModel.movie)
    )

async def set_status_canceled(
        db: AsyncSession,
        session_id: str | None = None,
        order: OrderModel | None = None,
) -> None:
    """
    Set the status of an order to CANCELED.

    This function cancels an order by setting its status to CANCELED
    if it is not already paid or canceled. You can either provide the order
    directly or specify the session_id to look up the order in the database.

    Args:
        db (AsyncSession): The asynchronous database session.
        session_id (str | None): The Stripe session ID used to find the order,
            if the order is not provided directly. Used when canceling an order
            through a Stripe webhook.
        order (OrderModel | None): An optional order instance used when
            canceling an order manually. If not provided, the order will be
            fetched using the session_id.

    Raises:
        HTTPException:
            - 404 if the order is not found (when using session_id).
            - 400 if the order is already paid.
            - 409 if the order is already canceled.
    """
    if order is None:
        stmt = select(OrderModel).where(OrderModel.session_id == session_id)
        result = await db.execute(stmt)
        order: OrderModel | None = result.scalars().one_or_none()
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found in your orders",
            )
    if order.status == OrderStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Order already paid"
        )
    if order.status == OrderStatus.CANCELED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Order already cancelled"
        )
    order.status = OrderStatus.CANCELED
    await db.commit()
