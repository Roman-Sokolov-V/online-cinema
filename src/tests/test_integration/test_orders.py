from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config import get_settings
from database import (
    OrderModel,
    OrderItemModel,
    OrderStatus,
)
from stripe_service.stripe_payment import create_stripe_session

BASE_URL = "/api/v1/orders/"


async def check_response(response, session, movies, detail):
    assert response.status_code == 201
    assert response.json().get("id") is not None
    order = await session.get(OrderModel, response.json().get("id"))
    assert order is not None
    created_at_str = response.json().get("created_at")
    print(created_at_str)
    created_at_dt = datetime.fromisoformat(created_at_str)
    assert created_at_dt == order.created_at
    assert set(response.json().get("movies")) == set(
        movie.name for movie in movies)
    assert set(item.movie_id for item in order.order_items) == set(
        movie.id for movie in movies)
    assert order.total_amount == sum(movie.price for movie in movies)
    assert response.json().get("total_amount") == str(order.total_amount)
    assert response.json().get("detail") == detail


async def check_responses(response, orders_in_db):
    for resp_order in response.json().get("orders"):
        assert resp_order.get("id") is not None
        assert resp_order.get("id") in [order.id for order in orders_in_db]
        for order in orders_in_db:
            if order.id == resp_order.get("id"):
                assert resp_order.get("created_at") is not None
                created_at_str = resp_order.get("created_at")
                print(created_at_str)
                created_at_dt = datetime.fromisoformat(created_at_str)
                assert created_at_dt == order.created_at
                assert resp_order.get("total_amount") == str(
                    order.total_amount)
                assert set(resp_order.get("movies")) == {
                    item.movie.name for item in order.order_items
                }


async def check_orders(movies, order, session_id):
    assert order is not None
    assert order.id is not None
    assert order.created_at is not None
    assert order.total_amount == sum(movie.price for movie in movies)
    assert order.status == OrderStatus.PENDING
    assert order.session_id == session_id
    assert order.order_items != []
    for item in order.order_items:
        assert item.movie_id in [movie.id for movie in movies]
        assert item.order_id == order.id
        for movie in movies:
            if movie.id == item.movie_id:
                assert item.price_at_order == movie.price


async def check_mocked_function(
        response, total_amount, movies, moked_kwargs, message, url
):
    assert response.headers["location"] == url
    assert moked_kwargs["total_amount"] == total_amount
    assert set(moked_kwargs["titles"].split(", ")) == set(movie.name for movie in movies)
    assert moked_kwargs["message"] == message


@patch("routes.orders.create_stripe_session")
@pytest.mark.asyncio
async def test_place_order_success(
        mock_create_session,
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_3_movies
):
    mock_checkout_session = MagicMock()
    mock_checkout_session.url = "https://fake-stripe-session.com"
    mock_checkout_session.id = "session_id"
    mock_create_session.return_value = mock_checkout_session

    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movies = get_3_movies

    for movie in movies:
        response = await client.post(f"/api/v1/cart/items/{movie.id}/",
                                     headers=header)
        assert response.status_code == 200

    response = await client.post(BASE_URL + "place/", headers=header)
    assert response.status_code == 303

    stmt = select(OrderModel)
    result = await db_session.execute(stmt)
    order = result.scalars().unique().one_or_none()
    mock_create_session.assert_called_once()
    args, kwargs = mock_create_session.call_args
    expected_message = "Thank you for your purchase."
    await check_orders(
        movies=movies,
        order=order,
        session_id=mock_checkout_session.id
    )
    mock_create_session.assert_called_once()
    await check_mocked_function(
        response=response,
        total_amount=sum(movie.price for movie in movies),
        movies=movies,
        moked_kwargs=kwargs,
        message=expected_message,
        url=mock_checkout_session.url
    )


@patch("routes.orders.create_stripe_session")
@pytest.mark.asyncio
async def test_place_order_movie_in_cart_deleted_from_db(
        mock_create_session,
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_3_movies
):
    mock_checkout_session = MagicMock()
    mock_checkout_session.url = "https://fake-stripe-session.com"
    mock_checkout_session.id = "session_id"
    mock_create_session.return_value = mock_checkout_session

    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movies = get_3_movies

    for movie in movies:
        response = await client.post(f"/api/v1/cart/items/{movie.id}/",
                                     headers=header)
        assert response.status_code == 200

    await db_session.delete(movies[0])
    await db_session.commit()
    movies = movies[1:]

    response = await client.post(BASE_URL + "place/", headers=header)
    assert response.status_code == 303
    stmt = select(OrderModel)
    result = await db_session.execute(stmt)
    order = result.scalars().unique().one_or_none()

    args, kwargs = mock_create_session.call_args
    expected_message = "Thank you for your purchase."

    await check_orders(
        movies=movies, order=order, session_id=mock_checkout_session.id
    )
    mock_create_session.assert_called_once()
    await check_mocked_function(
        response=response,
        total_amount=sum(movie.price for movie in movies),
        movies=movies,
        moked_kwargs=kwargs,
        message=expected_message,
        url=mock_checkout_session.url,
    )


@patch("routes.orders.create_stripe_session")
@pytest.mark.asyncio
async def test_place_order_some_movie_in_other_pending_order(
        mock_create_session,
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_3_movies
):
    mock_checkout_session = MagicMock()
    mock_checkout_session.url = "https://fake-stripe-session.com"
    mock_checkout_session.id = "session_id"
    mock_create_session.return_value = mock_checkout_session

    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movies = get_3_movies

    # create first order
    response = await client.post(f"/api/v1/cart/items/{movies[0].id}/",
                                 headers=header)
    assert response.status_code == 200

    response = await client.post(BASE_URL + "place/", headers=header)
    assert response.status_code == 303

    # create second order
    for movie in movies:
        response = await client.post(f"/api/v1/cart/items/{movie.id}/",
                                     headers=header)
        assert response.status_code == 200

    movie_in_other_order = movies[0]
    movies = movies[1:]

    response = await client.post(BASE_URL + "place/", headers=header)
    assert response.status_code == 303
    stmt = select(OrderModel).order_by(OrderModel.created_at.desc())
    result = await db_session.execute(stmt)
    orders = result.scalars().all()
    assert len(orders) == 2
    order = orders[0]

    args, kwargs = mock_create_session.call_args

    expected_message = (
            f"WARNING! Movies: {movie_in_other_order.name} have "
            f"not been added to the order because they are already in your "
            f"other orders awaiting payment."
        )

    await check_orders(
        movies=movies, order=order, session_id=mock_checkout_session.id
    )

    await check_mocked_function(
        response=response,
        total_amount=sum(movie.price for movie in movies),
        movies=movies,
        moked_kwargs=kwargs,
        message=expected_message,
        url=mock_checkout_session.url,
    )


@pytest.mark.asyncio
async def test_place_order_when_cart_is_empty(
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_3_movies
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movies = get_3_movies

    for movie in movies:
        response = await client.post(f"/api/v1/cart/items/{movie.id}/",
                                     headers=header)
        assert response.status_code == 200
    for movie in movies:
        await db_session.delete(movie)
    await db_session.commit()

    response = await client.post(BASE_URL + "place/", headers=header)
    assert response.status_code == 400
    assert response.json().get("detail") == "You don't have any items in cart."


@pytest.mark.asyncio
async def test_place_order_when_not_exist_yet(
        client,
        db_session,
        seed_database,
        create_activate_login_user
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    response = await client.post(BASE_URL + "place/", headers=header)
    assert response.status_code == 404
    assert response.json().get(
        "detail") == "Cart not found."


@pytest.mark.asyncio
async def test_admin_list_orders(
        client,
        db_session,
        seed_database,
        create_orders,
        create_activate_login_user,
):
    admin_data = await create_activate_login_user(group_name="admin")
    header = {"Authorization": f"Bearer {admin_data['access_token']}"}
    stmt = (
        select(OrderModel)
        .options(
            selectinload(OrderModel.order_items)
            .selectinload(OrderItemModel.movie)
        )
    )
    result = await db_session.execute(stmt)
    orders_in_db = result.scalars().all()

    response = await client.get(BASE_URL + "list/", headers=header)

    assert response.status_code == 200
    assert response.json().get("orders") is not None
    assert len(response.json().get("orders")) == 3

    await check_responses(response, orders_in_db)

@pytest.mark.asyncio
async def test_user_list_orders(
        client,
        db_session,
        seed_database,
        create_orders,
):
    data = create_orders
    user, header = data.get("users_data").get("user1")
    stmt = (
        select(OrderModel).where(OrderModel.user_id == user.id)
        .options(
            selectinload(OrderModel.order_items)
            .selectinload(OrderItemModel.movie)
        )
    )
    result = await db_session.execute(stmt)
    users_orders_in_db = result.scalars().all()

    response = await client.get(BASE_URL + "list/", headers=header)
    assert response.status_code == 200
    assert response.json().get("orders") is not None
    assert len(response.json().get("orders")) == 1
    for resp_order in response.json().get("orders"):
        assert resp_order["id"] in [order.id for order in users_orders_in_db]
    await check_responses(response, users_orders_in_db)


@pytest.mark.asyncio
async def test_user_try_list_other_user_orders(
        client,
        db_session,
        seed_database,
        create_orders,
):
    data = create_orders
    request_user, header = data.get("users_data").get("user1")

    stmt = (
        select(OrderModel).where(OrderModel.user_id == request_user.id)
        .options(
            selectinload(OrderModel.order_items)
            .selectinload(OrderItemModel.movie)
        )
    )
    result = await db_session.execute(stmt)
    users_orders_in_db = result.scalars().all()

    other_user, _ = data.get("users_data").get("user2")

    response = await client.get(
        BASE_URL + f"list/?user_id={other_user.id}", headers=header
    )
    assert response.status_code == 200
    assert response.json().get("orders") is not None
    assert len(response.json().get("orders")) == 1
    for resp_order in response.json().get("orders"):
        assert resp_order["id"] in [order.id for order in users_orders_in_db]
    await check_responses(response, users_orders_in_db)


@pytest.mark.asyncio
async def test_list_orders_with_filters(
        client,
        db_session,
        seed_database,
        create_orders,
        create_activate_login_user,
):
    admin_data = await create_activate_login_user(group_name="admin")
    header = {"Authorization": f"Bearer {admin_data['access_token']}"}

    data = create_orders
    filtered_user, _ = data.get("users_data").get("user3")

    stmt = (
        select(OrderModel).where(OrderModel.user_id == filtered_user.id)
        .options(
            selectinload(OrderModel.order_items)
            .selectinload(OrderItemModel.movie)
        )
    )
    result = await db_session.execute(stmt)
    expected_orders_in_db = result.scalars().all()

    # filter by user
    response = await client.get(
        BASE_URL + f"list/?user_id={filtered_user.id}", headers=header
    )

    assert response.status_code == 200
    assert response.json().get("orders") is not None

    assert len(response.json().get("orders")) == 1
    for resp_order in response.json().get("orders"):
        assert resp_order["id"] in [order.id for order in expected_orders_in_db]
    await check_responses(response, expected_orders_in_db)


    # pagination
    limit = 1
    offset = 1
    stmt = (
        select(OrderModel).limit(limit).offset(offset)
        .options(
            selectinload(OrderModel.order_items)
            .selectinload(OrderItemModel.movie)
        )
    )
    result = await db_session.execute(stmt)
    expected_orders_in_db = result.scalars().all()

    response = await client.get(
        BASE_URL + f"list/?offset={offset}&limit={limit}", headers=header
    )
    assert response.status_code == 200
    assert response.json().get("orders") is not None

    assert len(response.json().get("orders")) == 1
    for resp_order in response.json().get("orders"):
        assert resp_order["id"] in [order.id for order in expected_orders_in_db]
    await check_responses(response, expected_orders_in_db)

    # filter by date_from date_to

    stmt = select(OrderModel)
    result = await db_session.execute(stmt)
    orders = result.unique().scalars().all()

    order_2 = orders[1]
    order_3 = orders[2]
    order_3.created_at = datetime.now() - timedelta(days=10)
    order_2.created_at = datetime.now() - timedelta(days=5)
    await db_session.commit()

    date_from = datetime.now() - timedelta(days=7)
    date_to = datetime.now() - timedelta(days=2)

    stmt = select(OrderModel).where(
        (OrderModel.created_at > date_from) &
        (OrderModel.created_at < date_to)
    )
    result = await db_session.execute(stmt)
    expected_orders_in_db = result.unique().scalars().all()
    assert len(expected_orders_in_db) == 1
    assert expected_orders_in_db[0].created_at == order_2.created_at

    response = await client.get(
        BASE_URL + f"list/?date_from={date_from}&date_to={date_to}",
        headers=header
    )

    assert response.status_code == 200
    assert response.json().get("orders") is not None

    assert len(response.json().get("orders")) == 1
    for resp_order in response.json().get("orders"):
        assert resp_order["id"] in [order.id for order in
                                    expected_orders_in_db]
    await check_responses(response, expected_orders_in_db)


    # filter by status
    status = "paid"
    order_3.status = "paid"
    await db_session.commit()

    response = await client.get(
        BASE_URL + f"list/?status={status}",
        headers=header
    )
    assert response.status_code == 200
    assert response.json().get("orders") is not None
    assert len(response.json().get("orders")) == 1
    assert response.json().get("orders")[0]["id"] == order_3.id


def test_create_stripe_session():
    settings = get_settings()
    message = "ok"
    total_amount=Decimal(5)
    order_id = 1
    stripe_session = create_stripe_session(
        total_amount=total_amount,
        titles="DieHard",
        message=message,
        order_id=order_id,
    )
    assert stripe_session is not None
    assert stripe_session.url is not None
    assert stripe_session.id is not None
    assert stripe_session.url.startswith("https://checkout.stripe.com/")
    assert stripe_session.id.startswith("cs_test")
    assert stripe_session.object == "checkout.session"
    assert stripe_session.mode == "payment"
    assert stripe_session.success_url == settings.PAYMENT_SUCCESS_URL + f"{order_id}/"
    assert stripe_session.cancel_url == settings.PAYMENT_CANCEL_URL + f"{order_id}/"
    assert stripe_session.custom_text.submit["message"] == message
    assert stripe_session.amount_total == total_amount * 100
