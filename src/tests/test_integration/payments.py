import pytest
import pytest_asyncio

from sqlalchemy import select

from config import get_settings
from database import OrderModel, PaymentModel, UserModel
from database.populate import CSVDatabaseSeeder
from routes.crud.payments import create_payment
from schemas import PaymentsHistorySchema, PaymentSchema
from tests.conftest import db_session
from tests.test_integration.test_orders import BASE_URL as ORDERS_BASE_URL
from tests.test_integration.test_shoping_cart import BASE_URL as CART_BASE_URL

BASE_URL = "/api/v1/payments/"

@pytest_asyncio.fixture()
async def create_payments_get_users_data(seed_database, get_9_movies, client, create_activate_login_user, db_session):
    movies = get_9_movies

    prefix = 1
    users_data = []
    while prefix <= 3:
        user_data = await create_activate_login_user(prefix=str(prefix))
        users_data.append(user_data)
        prefix += 1
    index_0, index_1 = 0, 3
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
    assert len(all_orders) == 9

    for order in all_orders:
        await create_payment(db=db_session, session_id=order.session_id)
    return users_data


@pytest.mark.asyncio
async def test_history_payments(client, db_session, create_payments_get_users_data):
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

        assert sorted(response.json()["payments"], key=lambda p: p["id"]) == sorted(
            [
                PaymentSchema.model_validate(payment).model_dump(mode="json")
                for payment in user_payments_in_db
            ],
            key=lambda p: p["id"],
        )
