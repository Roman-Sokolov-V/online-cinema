import pytest
from sqlalchemy import select

from database import CartModel, CartItemModel, PurchaseModel

BASE_URL = "/api/v1/cart/"


@pytest.mark.asyncio
async def test_add_movie_to_cart_that_not_exists_yet(
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_movie
):
    user_data = await create_activate_login_user()
    user = user_data["user"]
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movie = get_movie
    response = await client.post(BASE_URL + f"items/{movie.id}/",
                                 headers=header)
    assert response.status_code == 200

    stmt = select(CartModel)
    result = await db_session.execute(stmt)
    cart_db = result.scalars().first()
    assert cart_db is not None
    assert len(cart_db.cart_items) == 1
    item_db = cart_db.cart_items[0]
    assert item_db.cart_id == cart_db.id
    assert item_db.movie_id == movie.id
    assert cart_db.user_id == user.id

    assert response.json().get("id") == cart_db.id
    assert len(response.json().get("cart_items")) == 1
    item_response = response.json().get("cart_items")[0]

    assert item_response.get("id") is not None
    assert item_response.get("movie_id") == movie.id
    movie_response = item_response.get("movie")
    assert movie_response is not None
    assert movie_response.get("name") == movie.name
    assert movie_response.get("uuid") == str(movie.uuid)
    assert movie_response.get("year") == movie.year
    assert movie_response.get("time") == movie.time
    assert movie_response.get("imdb") == movie.imdb
    assert movie_response.get("meta_score") == movie.meta_score
    assert movie_response.get("gross") == movie.gross
    assert movie_response.get("description") == movie.description
    assert movie_response.get("price") == str(movie.price)


@pytest.mark.asyncio
async def test_add_movie_to_exists_cart(
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_3_movies
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movie_1, movie_2, _ = get_3_movies
    response = await client.post(
        BASE_URL + f"items/{movie_1.id}/", headers=header
    )
    assert response.status_code == 200
    stmt = select(CartModel)
    result = await db_session.execute(stmt)
    exists_cart_db = result.scalars().first()

    response = await client.post(
        BASE_URL + f"items/{movie_2.id}/", headers=header
    )
    assert response.status_code == 200

    stmt = select(CartModel)
    result = await db_session.execute(stmt)
    carts_db = result.unique().scalars().all()

    assert len(carts_db) == 1, "Should not be created second cart"

    assert carts_db[
               0] is exists_cart_db, "Should not be deleted old and created new one cart"
    cart = carts_db[0]
    await db_session.refresh(cart, attribute_names=["cart_items"])
    cart_items = cart.cart_items
    assert len(cart_items) == 2
    movies_ids_in_cart = (item.movie_id for item in cart.cart_items)
    assert movie_1.id in movies_ids_in_cart, "In cart should exists movie_1"
    assert movie_2.id in movies_ids_in_cart, "In cart should exists movie_2"


@pytest.mark.asyncio
async def test_add_movie_twice_to_cart(
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_movie
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movie = get_movie
    response = await client.post(
        BASE_URL + f"items/{movie.id}/", headers=header
    )
    assert response.status_code == 200
    stmt = select(CartModel)
    result = await db_session.execute(stmt)
    exists_cart_db = result.scalars().first()

    response = await client.post(
        BASE_URL + f"items/{movie.id}/", headers=header
    )
    assert response.status_code == 400
    assert response.json().get(
        "detail") == "Movie already exists in shopping cart."


@pytest.mark.asyncio
async def test_add_already_purchased_movie_to_cart(
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_movie
):
    user_data = await create_activate_login_user()
    user = user_data.get("user")
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movie = get_movie
    purchased = PurchaseModel(user_id=user.id, movie_id=movie.id)
    db_session.add(purchased)
    await db_session.commit()
    await db_session.refresh(purchased)

    response = await client.post(
        BASE_URL + f"items/{movie.id}/", headers=header
    )
    assert response.status_code == 400
    assert response.json().get(
        "detail") == "You already purchased this movie."


@pytest.mark.asyncio
async def test_remove_movie_from_cart_success(
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_movie
):
    user_data = await create_activate_login_user()
    user = user_data.get("user")
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movie = get_movie
    response = await client.post(BASE_URL + f"items/{movie.id}/",
                                 headers=header)
    assert response.status_code == 200

    response = await client.delete(
        BASE_URL + f"items/{movie.id}/", headers=header
    )
    assert response.status_code == 200
    stmt = select(CartModel).where(CartModel.user_id == user.id)
    result = await db_session.execute(stmt)
    exists_cart_db = result.scalars().first()
    assert movie.id not in (item.movie_id for item in
                            exists_cart_db.cart_items), "Movie should not be in cart"


async def test_remove_movie_that_not_exists_in_cart(
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_3_movies
):
    user_data = await create_activate_login_user()
    user = user_data.get("user")
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movie_1, movie_2, _ = get_3_movies
    response = await client.post(BASE_URL + f"items/{movie_1.id}/",
                                 headers=header)
    assert response.status_code == 200

    response = await client.delete(
        BASE_URL + f"items/{movie_2.id}/", headers=header
    )
    assert response.status_code == 400
    assert response.json().get(
        "detail") == "Movie not exists in shopping cart."


async def test_remove_movie_that_not_exists_in_db(
        client,
        db_session,
        seed_database,
        create_activate_login_user,
        get_movie
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    movie = get_movie
    response = await client.post(BASE_URL + f"items/{movie.id}/",
                                 headers=header)
    assert response.status_code == 200

    response = await client.delete(
        BASE_URL + f"items/{100000}/", headers=header
    )
    assert response.status_code == 404
    assert response.json().get(
        "detail") == "Movie with the ID provided does not exist."


async def test_list_empty_cart(
        client,
        db_session,
        create_activate_login_user,
):
    user_data = await create_activate_login_user()
    user = user_data["user"]
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()
    response = await client.get(BASE_URL + f"items/", headers=header)
    assert response.status_code == 200

    await db_session.refresh(cart, attribute_names=["cart_items"])
    assert response.json().get("cart_items") == []


async def test_list_cart_items_if_cart_not_exists(
        client,
        db_session,
        create_activate_login_user,
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}

    response = await client.get(BASE_URL + f"items/", headers=header)
    assert response.status_code == 404
    assert response.json().get(
        "detail") == "You do not have shopping cart yet."
