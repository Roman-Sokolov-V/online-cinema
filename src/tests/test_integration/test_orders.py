from datetime import datetime, timezone

import pytest
from sqlalchemy import select, delete

from database import CartModel, PurchaseModel, OrderModel, MovieModel

BASE_URL = "/api/v1/orders/"


async def check_response(response, session, movies, detail):
    assert response.status_code == 201
    assert response.json().get("id") is not None
    order = await session.get(OrderModel, response.json().get("id"))
    assert order is not None
    created_at_str = response.json().get("created_at")
    created_at_dt = datetime.fromisoformat(created_at_str)
    assert created_at_dt == order.created_at.replace(tzinfo=timezone.utc)
    assert set(response.json().get("movies")) == set(
        movie.name for movie in movies)
    assert set(item.movie_id for item in order.order_items) == set(
        movie.id for movie in movies)
    assert order.total_amount == sum(movie.price for movie in movies)
    assert response.json().get("total_amount") == str(order.total_amount)
    assert response.json().get("detail") == detail


@pytest.mark.asyncio
async def test_place_order_success(
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

    response = await client.post(BASE_URL + "place/", headers=header)
    await check_response(
        response=response,
        session=db_session,
        movies=movies,
        detail="Movies from the cart added to the order successfully."
    )


@pytest.mark.asyncio
async def test_place_order_movie_in_cart_deleted_from_db(
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

    await db_session.delete(movies[0])
    await db_session.commit()
    movies = movies[1:]

    response = await client.post(BASE_URL + "place/", headers=header)
    await check_response(
        response=response,
        session=db_session,
        movies=movies,
        detail="Movies from the cart added to the order successfully."
    )


@pytest.mark.asyncio
async def test_place_order_some_movie_in_other_pending_order(
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_3_movies
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movies = get_3_movies

    # create first order
    response = await client.post(f"/api/v1/cart/items/{movies[0].id}/",
                                 headers=header)
    assert response.status_code == 200

    response = await client.post(BASE_URL + "place/", headers=header)
    assert response.status_code == 201

    # create second order
    for movie in movies:
        response = await client.post(f"/api/v1/cart/items/{movie.id}/",
                                     headers=header)
        assert response.status_code == 200

    movie_in_other_order = movies[0]
    movies = movies[1:]

    expected_detail = (
        f"Movies from the cart added to the order successfully. Movies with "
        f"the following IDs: {[movie_in_other_order.id]} have not been added "
        f"to the order because they are already in your other orders "
        f"awaiting payment."
    )
    response = await client.post(BASE_URL + "place/", headers=header)
    await check_response(
        response=response,
        session=db_session,
        movies=movies,
        detail=expected_detail
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

    #
    # stmt = select(CartModel)
    # result = await db_session.execute(stmt)
    # cart_db = result.scalars().first()
    # assert cart_db is not None
    # assert len(cart_db.cart_items) == 1
    # item_db = cart_db.cart_items[0]
    # assert item_db.cart_id == cart_db.id
    # assert item_db.movie_id == movie.id
    # assert cart_db.user_id == user.id
    #
    # assert response.json().get("id") == cart_db.id
    # assert len(response.json().get("cart_items")) == 1
    # item_response = response.json().get("cart_items")[0]
    #
    # assert item_response.get("id") is not None
    # assert item_response.get("movie_id") == movie.id
    # movie_response = item_response.get("movie")
    # assert movie_response is not None
    # assert movie_response.get("name") == movie.name
    # assert movie_response.get("uuid") == str(movie.uuid)
    # assert movie_response.get("year") == movie.year
    # assert movie_response.get("time") == movie.time
    # assert movie_response.get("imdb") == movie.imdb
    # assert movie_response.get("meta_score") == movie.meta_score
    # assert movie_response.get("gross") == movie.gross
    # assert movie_response.get("description") == movie.description
    # assert movie_response.get("price") == str(movie.price)
