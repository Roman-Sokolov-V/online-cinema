from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from assertpy import assert_that # type: ignore
from sqlalchemy import select

from database import OrderModel, StatusPayment, OrderStatus, PaymentModel
from routes.crud.payments import create_payment
from schemas import  PaymentSchema

from tests.test_integration.test_orders import BASE_URL as ORDERS_BASE_URL
from tests.test_integration.test_shoping_cart import BASE_URL as CART_BASE_URL



BASE_URL = "/api/v1/payments/"

@pytest_asyncio.fixture()
async def create_payments_get_users_data(seed_database, get_12_movies, client, create_activate_login_user, db_session):
    movies = get_12_movies
    prefix = 1
    users_data = []
    # create 3 users
    while prefix <= 3:
        user_data = await create_activate_login_user(prefix=str(prefix))
        users_data.append(user_data)
        prefix += 1
    index_0, index_1 = 0, 4
    #for each user create 4 payments, total 12 payments
    for user_data in users_data:
        users_movies = movies[index_0:index_1]
        header = {"Authorization": f"Bearer {user_data['access_token']}"}
        for movie in users_movies:
            response = await client.post(
                CART_BASE_URL + f"items/{movie.id}/", headers=header)

            assert response.status_code == 200
            response = await client.post(
                ORDERS_BASE_URL + "place/", headers=header
            )
            assert response.status_code == 303

        index_0 += 3
        index_1 += 3
    stmt = select(OrderModel)
    result = await db_session.execute(stmt)
    all_orders = result.scalars().all()
    assert len(all_orders) == 12

    for order in all_orders:
        await create_payment(db=db_session, session_id=order.session_id)
    return users_data


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


@pytest.mark.asyncio
async def test_history_payments(
        client,
        db_session,
        create_payments_get_users_data
):
    users_data = create_payments_get_users_data

    for user_data in users_data:
        user = user_data["user"]
        stmt = select(PaymentModel).where(PaymentModel.user_id == user.id)
        result = await db_session.execute(stmt)
        user_payments_in_db = result.scalars().all()
        header = {"Authorization": f"Bearer {user_data['access_token']}"}
        response = await client.get(BASE_URL, headers=header)
        assert response.status_code == 200
        assert len(response.json()["payments"]) == len(user_payments_in_db)

        assert sorted(
            response.json()["payments"], key=lambda p: p["id"]
        ) == sorted(
            [
                PaymentSchema.model_validate(payment).model_dump(mode="json")
                for payment in user_payments_in_db
            ],
            key=lambda p: p["id"],
        )


@pytest.mark.asyncio
async def test_all_payment_check_permissions(
        client,
        db_session,
        create_payments_get_users_data,
        create_activate_login_user
):
    users_data = create_payments_get_users_data
    admin_data = await create_activate_login_user(group_name="admin")
    moderator_data = await create_activate_login_user(group_name="moderator")
    for user_data in users_data:
        header = {"Authorization": f"Bearer {user_data['access_token']}"}
        response = await client.get(BASE_URL + "all/", headers=header)
        assert response.status_code == 403, "Regular user should not have permissions"

    header = {"Authorization": f"Bearer {admin_data['access_token']}"}
    response = await client.get(BASE_URL + "all/", headers=header)
    assert response.status_code != 403, "Admin user should have permissions"
    header = {"Authorization": f"Bearer {moderator_data['access_token']}"}
    response = await client.get(BASE_URL + "all/", headers=header)
    assert response.status_code != 403, "Moderator should have no permissions"

@pytest.mark.asyncio
async def test_all_payment_success(
        client,
        db_session,
        create_payments_get_users_data,
        create_activate_login_user
):
    stmt = select(PaymentModel).order_by(PaymentModel.created_at.desc())
    result = await db_session.execute(stmt)
    all_payments = result.scalars().all()
    assert len(all_payments) == 12
    first_10_payments = all_payments[:10]


    admin_data = await create_activate_login_user(group_name="admin")

    header = {"Authorization": f"Bearer {admin_data['access_token']}"}
    response = await client.get(BASE_URL + "all/", headers=header)
    assert response.status_code == 200, "Expected 200"
    assert len(response.json()["payments"]) == 10
    assert response.json()["items"] == 12
    assert response.json()["payments"] == [
                PaymentSchema.model_validate(payment).model_dump(mode="json")
                for payment in first_10_payments
            ]


@pytest.mark.asyncio
async def test_all_payment_filters(
        client,
        db_session,
        create_payments_get_users_data,
        create_activate_login_user
):
    stmt = select(PaymentModel).order_by(PaymentModel.created_at.desc())
    result = await db_session.execute(stmt)
    all_payments = result.scalars().all()
    assert len(all_payments) == 12
    limit = 3
    offset = 2
    expected_payments = all_payments[offset:(limit + offset)]

    admin_data = await create_activate_login_user(group_name="admin")

    header = {"Authorization": f"Bearer {admin_data['access_token']}"}

    # pagination
    response = await client.get(
        BASE_URL + f"all/?limit={limit}&offset={offset}", headers=header
    )
    assert response.status_code == 200, "Expected 200"
    assert len(response.json()["payments"]) == limit
    assert response.json()["items"] == 12
    assert (
        response.json()["next_page"]
        == f"{BASE_URL}all/?limit={limit}&offset={limit + offset}&user_id=None&date_from=None&date_to=None&status=None"
    )
    assert (
        response.json()["prev_page"]
        == f"{BASE_URL}all/?limit={limit}&offset=0&user_id=None&date_from=None&date_to=None&status=None"
    )
    assert response.json()["payments"] == [
                PaymentSchema.model_validate(payment).model_dump(mode="json")
                for payment in expected_payments
            ]

    # date filter
    expected_payments = all_payments[:3]
    shift_days = 5
    for payment in expected_payments:
        payment.created_at = datetime.now() - timedelta(days=shift_days)
        shift_days += 1
    await db_session.commit()
    date_from = datetime.now() - timedelta(days=shift_days)
    date_to = datetime.now() - timedelta(days=1)
    response = await client.get(
        BASE_URL + f"all/?date_from={date_from}&date_to={date_to}", headers=header
    )
    assert response.status_code == 200, "Expected 200"
    assert len(response.json()["payments"]) == 3
    assert response.json()["items"] == 3
    assert response.json()["payments"] == [
        PaymentSchema.model_validate(payment).model_dump(mode="json")
        for payment in expected_payments
    ]

    # user_id filter
    users_data = create_payments_get_users_data
    user_id = users_data[0]["user"].id

    stmt = select(PaymentModel).where(PaymentModel.user_id == user_id).order_by(PaymentModel.created_at.desc())
    result = await db_session.execute(stmt)
    all_user_payments = result.scalars().all()
    expected_payments =all_user_payments[:10]
    response = await client.get(
        BASE_URL + f"all/?user_id={user_id}", headers=header
    )
    assert response.status_code == 200, "Expected 200"
    assert len(response.json()["payments"]) == len(expected_payments)
    assert response.json()["items"] == len(all_user_payments)
    assert (
        response.json()["next_page"]
        == f"{BASE_URL}all/?limit=10&offset=0&user_id={user_id}&date_from=None&date_to=None&status=None"
    )
    assert (
        response.json()["prev_page"]
        == f"{BASE_URL}all/?limit=10&offset=0&user_id={user_id}&date_from=None&date_to=None&status=None"
    )
    assert response.json()["payments"] == [
        PaymentSchema.model_validate(payment).model_dump(mode="json")
        for payment in expected_payments
    ]

    # status filter
    status = "refunded"
    expected_payments = all_payments[10:]
    for payment in expected_payments:
        payment.status = status
    await db_session.commit()

    response = await client.get(BASE_URL + f"all/?status={status}", headers=header)
    assert response.status_code == 200, "Expected 200"
    assert len(response.json()["payments"]) == len(expected_payments)
    assert response.json()["items"] == len(expected_payments)
    assert (
        response.json()["next_page"]
        == f"{BASE_URL}all/?limit=10&offset=0&user_id=None&date_from=None&date_to=None&status={status}"
    )
    assert (
        response.json()["prev_page"]
        == f"{BASE_URL}all/?limit=10&offset=0&user_id=None&date_from=None&date_to=None&status={status}"
    )
    assert response.json()["payments"] == [
        PaymentSchema.model_validate(payment).model_dump(mode="json")
        for payment in expected_payments
    ]
