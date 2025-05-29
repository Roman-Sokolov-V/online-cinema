from fastapi import HTTPException, status

from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select


from database import PaymentModel, OrderModel, PaymentItemModel, OrderStatus


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
            detail=f"Unexpected error: {getattr(e, 'orig', str(e))}, while creating payment"
        )
