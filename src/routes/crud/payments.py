from typing import List, Sequence

from fastapi import HTTPException, status

from sqlalchemy.sql import Select
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy import select


from database import PaymentModel, OrderModel, PaymentItemModel, OrderStatus
from schemas import PaymentsFilterParams


async def create_payment(db: AsyncSession, session_id: str):
    stmt = select(OrderModel).where(OrderModel.session_id == session_id)
    result = await db.execute(stmt)
    order = result.scalars().first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    try:
        payment = PaymentModel(
            order=order,
            user_id=order.user_id,
            amount=order.total_amount,
            external_payment_id=session_id
        )
        db.add(payment)

        for order_item in order.order_items:
            payment_item = PaymentItemModel(
                payment=payment,
                order_item=order_item,
                price_at_payment=order_item.price_at_order,
            )
            db.add(payment_item)

        order.status = OrderStatus.PAID

        await db.commit()
        await db.refresh(payment)
        return payment
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Integrity error: {getattr(e, 'orig', str(e))}"
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {getattr(e, 'orig', str(e))}, "
                   f"while creating payment"
        )


async def get_users_payments(db: AsyncSession, user_id: int) -> Sequence[PaymentModel]:
    stmt = select(PaymentModel).where(PaymentModel.user_id == user_id)
    result = await db.execute(stmt.order_by(PaymentModel.created_at.desc()))
    payments = result.scalars().all()
    return payments


def get_filtered_stmt(
        filtered_query: PaymentsFilterParams
) -> Select:

    stmt = select(PaymentModel)
    if filtered_query.user_id is not None:
        stmt = stmt.where(PaymentModel.user_id == filtered_query.user_id)
    if filtered_query.date_from is not None:
        stmt = stmt.where(PaymentModel.created_at >= filtered_query.date_from)
    if filtered_query.date_to is not None:
        stmt = stmt.where(PaymentModel.created_at <= filtered_query.date_to)
    if filtered_query.status is not None:
        stmt = stmt.where(PaymentModel.status == filtered_query.status)
    return stmt

    # if filtered_query.offset is not None:
    #     stmt = stmt.offset(filtered_query.offset)
    # if filtered_query.limit is not None:
    #     stmt = stmt.limit(filtered_query.limit)
    return stmt

def paginate_stmt(
        stmt: Select,
        filtered_query: PaymentsFilterParams,
) -> Select:
    if filtered_query.offset is not None:
        stmt = stmt.offset(filtered_query.offset)
    if filtered_query.limit is not None:
        stmt = stmt.limit(filtered_query.limit)
    return stmt


# def get_all_filtered_users_payments(
#         db: AsyncSession,
#         filtered_query: PaymentsFilterParams
# ) -> Sequence[PaymentModel]:
#     stmt = filtered_stmt(filtered_query)
#     result = await db.execute(stmt.order_by(PaymentModel.created_at.desc()))
#     return payments
