import pytest
from assertpy import assert_that
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from database import OrderModel, StatusPayment, OrderStatus, PaymentModel
from routes.crud.payments import create_payment

BASE_URL = "/api/v1/webhooks/"



def check_payment(payment: PaymentModel, order: OrderModel):
    assert_that(payment, "Payment is None").is_not_none()
    assert_that(payment.id, "Payment ID is None").is_not_none()
    assert_that(payment.user_id, "Unexpected user_id").is_equal_to(order.user_id)
    assert_that(payment.order_id, "Unexpected order_id").is_equal_to(order.id)
    assert_that(payment.created_at, "Payment has no creation timestamp").is_not_none()
    assert_that(payment.status, "Wrong payment status").is_equal_to(StatusPayment.SUCCESSFUL)
    assert_that(payment.amount, "Wrong payment amount").is_equal_to(order.total_amount)
    assert_that(payment.external_payment_id, "Wrong external_payment_id").is_equal_to(order.session_id)

    payment_item_ids = {p.order_item_id for p in payment.payment_items}
    order_item_ids = {o.id for o in order.order_items}
    assert_that(payment_item_ids, "Mismatch between payment and order items").is_equal_to(order_item_ids)

    assert_that(order.status, "Order is not marked as PAID").is_equal_to(OrderStatus.PAID)


@pytest.mark.asyncio
async def test_create_payment(
        db_session,
        seed_database,
        create_orders,
):
    stmt = select(OrderModel).limit(1)
    result = await db_session.execute(stmt)
    order = result.scalars().first()

    assert order is not None
    assert order.status == OrderStatus.PENDING

    payment = await create_payment(db=db_session, session_id=order.session_id)
    await db_session.refresh(order)
    check_payment(payment=payment, order=order)



@patch("routes.webhooks.stripe.Webhook.construct_event")
@pytest.mark.asyncio
async def test_webhook(
        mock_constract_event,
        client,
        db_session,
        seed_database,
        create_orders,
):
    stmt = select(OrderModel).limit(1)
    result = await db_session.execute(stmt)
    order = result.scalars().first()

    assert order is not None
    assert order.status == OrderStatus.PENDING
    session_id = order.session_id

    mock_event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": session_id}},
    }
    mock_constract_event.return_value = mock_event

    response = await client.post(BASE_URL, json={})
    assert response.status_code == 200
    mock_constract_event.assert_called_once()

    stmt = select(PaymentModel)
    result = await db_session.execute(stmt)
    payment = result.scalars().first()
    await db_session.refresh(order)

    check_payment(payment=payment, order=order)
