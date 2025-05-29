from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import Select
from sqlalchemy.orm import selectinload
from database import OrderModel, OrderStatus, MovieModel, OrderItemModel
from schemas import FilterParams


def get_orders_stmt(
        filtered_query: FilterParams
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

async def set_status_canceled(session_id: str, db: AsyncSession) -> None:
    stmt = select(OrderModel).where(OrderModel.session_id == session_id)
    result = await db.execute(stmt)
    order = result.scalars().one_or_none()
