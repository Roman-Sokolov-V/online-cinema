import pytest
from unittest.mock import patch
from sqlalchemy import select

from database import OrderModel, OrderStatus, PaymentModel, StatusPayment

BASE_URL = "/api/v1/webhooks/"

@patch("routes.webhooks.stripe.Webhook.construct_event")
@pytest.mark.asyncio
async def test_webhook_received_completed(
        mocked_event,
        db_session,
        client,
        seed_database,
        create_orders
):
    stmt = select(OrderModel).limit(1)
    result = await db_session.execute(stmt)
    order = result.scalars().first()
    assert order is not None
    assert order.status == OrderStatus.PENDING

    stmt = select(PaymentModel)
    result = await db_session.execute(stmt)
    payment = result.scalars().first()
    assert payment is None

    mocked_event.return_value = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": order.session_id,
            }
        }
    }
    response = await client.post(BASE_URL)
    assert response.status_code == 200
    await db_session.refresh(order)
    assert order.status == OrderStatus.PAID
    stmt = select(PaymentModel)
    result = await db_session.execute(stmt)
    payment = result.scalars().one_or_none()
    assert payment is not None
    assert payment.external_payment_id == order.session_id
    assert payment.order_id == order.id
    assert payment.user_id == order.user_id
    assert payment.status == StatusPayment.SUCCESSFUL


@patch("routes.webhooks.stripe.Webhook.construct_event")
@pytest.mark.asyncio
async def test_webhook_received_cancelled(
        mocked_event,
        db_session,
        client,
        seed_database,
        create_orders
):
    stmt = select(OrderModel).limit(1)
    result = await db_session.execute(stmt)
    order = result.scalars().one_or_none()
    assert order is not None
    assert order.status == OrderStatus.PENDING

    mocked_event.return_value = {
        "type": "payment_intent.canceled",
        "data": {
            "object": {
                "id": order.session_id,
            }
        }
    }
    response = await client.post(BASE_URL)
    assert response.status_code == 200
    await db_session.refresh(order)
    assert order.status == OrderStatus.CANCELED
    stmt = select(PaymentModel)
    result = await db_session.execute(stmt)
    payment = result.scalars().one_or_none()
    assert payment is None


@patch("routes.webhooks.stripe.Webhook.construct_event")
@pytest.mark.asyncio
async def test_webhook_received_expired(
        mocked_event,
        db_session,
        client,
        seed_database,
        create_orders
):
    stmt = select(OrderModel).limit(1)
    result = await db_session.execute(stmt)
    order = result.scalars().one_or_none()
    assert order is not None
    assert order.status == OrderStatus.PENDING

    mocked_event.return_value = {
        "type": "checkout.session.expired",
        "data": {
            "object": {
                "id": order.session_id,
            }
        }
    }
    response = await client.post(BASE_URL)
    assert response.status_code == 200
    await db_session.refresh(order)
    assert order.status == OrderStatus.CANCELED
    stmt = select(PaymentModel)
    result = await db_session.execute(stmt)
    payment = result.scalars().one_or_none()
    assert payment is None
