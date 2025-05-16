from random import choice

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import GenreModel, MovieModel

from sqlalchemy import insert

from schemas import MovieBaseSchema

Base_URL = "/api/v1/theater/genres/"


@pytest.fixture(scope="function")
async def create_genre(db_session):
    stmt = insert(GenreModel).values(
        [
            {"name": "action"},
            {"name": "horror"},
            {"name": "adventure"},
        ]
    )
    await db_session.execute(stmt)
    await db_session.commit()
    stmt = select(GenreModel)
    result = await db_session.execute(stmt)
    genres = result.scalars().all()
    return genres


@pytest.mark.asyncio
async def test_permission(client, db_session, create_activate_login_user):
    user_data = await create_activate_login_user(group_name="user")
    user_header = {"Authorization": f"Bearer {user_data['access_token']}"}

    admin_data = await create_activate_login_user(group_name="admin")
    admin_header = {"Authorization": f"Bearer {admin_data['access_token']}"}

    moderator_data = await create_activate_login_user(group_name="moderator")
    moderator_header = {
        "Authorization": f"Bearer {moderator_data['access_token']}"}

    response = await client.post(Base_URL, json={"name": "fairytale"},
                                 headers=user_header)
    assert response.status_code == 403, "User does not have enough permissions"

    response = await client.post(Base_URL, json={"name": "fairytale"},
                                 headers=admin_header)
    assert response.status_code != 403, "Admin should has permissions, to create genre"
    assert response.status_code == 201, "Expected code 201, if create genre successful"

    response = await client.post(Base_URL, json={"name": "drama"},
                                 headers=moderator_header)
    assert response.status_code != 403, "Moderator shold has permissions, to create a genre"
    assert response.status_code == 201, "Expected code 201, if create genre successful"

    stmt = select(GenreModel.id)
    result = await db_session.execute(stmt)
    genre_ids = result.scalars().all()
    assert len(genre_ids) == 2, "Should be 2 genres in db"
    genre_id = genre_ids[0]
    genre_id_2 = genre_ids[1]

    response = await client.patch(
        f"/api/v1/theater/genres/{genre_id}/",
        json={"name": "action"}, headers=user_header
    )
    assert response.status_code == 403, "User shold not has permissions to patch genre"

    response = await client.patch(
        f"/api/v1/theater/genres/{genre_id}/",
        json={"name": "comedy"}, headers=admin_header
    )
    assert response.status_code != 403, "Admin shold has permissions, to patch genre"
    assert response.status_code == 200, "Expected code 200, if patch successful"

    response = await client.patch(
        f"/api/v1/theater/genres/{genre_id}/",
        json={"name": "horror"}, headers=moderator_header
    )
    assert response.status_code != 403, "Moderator shold has permissions, to patch genre"
    assert response.status_code == 200, "Expected code 200, if patch successful"

    response = await client.patch(
        f"/api/v1/theater/genres/{genre_id}/",
        json={"name": "action"}, headers=user_header
    )
    assert response.status_code == 403, "User shold not have permissions to patch genre"

    response = await client.patch(
        f"/api/v1/theater/genres/{genre_id}/",
        json={"name": "comedy"}, headers=admin_header
    )
    assert response.status_code != 403, "Admin shold has permissions, to patch genre"
    assert response.status_code == 200, "Expected code 200, if patch successful"

    response = await client.patch(
        f"/api/v1/theater/genres/{genre_id}/",
        json={"name": "horror"}, headers=moderator_header
    )
    assert response.status_code != 403, "Moderator shold has permissions, to patch genre"
    assert response.status_code == 200, "Expected code 200, if patch successful"


@pytest.mark.asyncio
async def test_genre_create_successfully(auth_client, db_session):
    create_data = {"name": "new_genre"}
    response = await auth_client.post(Base_URL, json=create_data)
    assert response.status_code == 201, "Expected 201 Created"
    stmt = select(GenreModel).where(GenreModel.name == "new_genre")
    result = await db_session.execute(stmt)
    genre_db = result.scalars().first()
    assert genre_db is not None, "Genre was not created"
    assert (
            genre_db.id == response.json()["id"]
            and genre_db.name == response.json()["name"] == create_data["name"]
    ), "Response data and db data does not match"


@pytest.mark.asyncio
async def test_genre_create_with_exists_genre_name(auth_client, db_session):
    create_data = {"name": "new_genre"}
    response = await auth_client.post(Base_URL, json=create_data)
    assert response.status_code == 201, "Expected 201 Created"

    stmt = select(GenreModel).where(GenreModel.name == "new_genre")
    result = await db_session.execute(stmt)
    exists_genre_db = result.scalars().first()

    response = await auth_client.post(Base_URL, json=create_data)

    assert response.status_code == 409, "Expected 409 Conflict"

    stmt = select(GenreModel).where(GenreModel.name == "new_genre")
    result = await db_session.execute(stmt)
    genres = result.scalars().all()
    assert len(genres) == 1, "Genre-name should be unique"
    updated_genre_db = genres[0]
    assert exists_genre_db == updated_genre_db, "Exists genre, should not be deleted"


@pytest.mark.asyncio
async def test_delete_genre_success(auth_client, db_session, create_genre):
    genre, _, _ = create_genre
    response = await auth_client.delete((Base_URL + f"{genre.id}/"))
    assert response.status_code == 204, "Expected code 204, delete successfully"
    genre_db = await db_session.scalar(
        select(GenreModel).where(GenreModel.id == genre.id))
    assert genre_db is None, "Genre should be deleted"


@pytest.mark.asyncio
async def test_delete_not_exist_genre(auth_client, db_session):
    response = await auth_client.delete((Base_URL + f"100/"))
    assert response.status_code == 404, "Expected code 404, Genre not found"


@pytest.mark.asyncio
async def test_update_genre_success(auth_client, db_session, create_genre):
    genre, _, _ = create_genre
    update_data = {"name": "new_genre"}
    assert genre.name != update_data["name"], "Names should not be the same"
    response = await auth_client.patch((Base_URL + f"{genre.id}/"),
                                       json=update_data)
    assert response.status_code == 200, "Expected code 200, genre updated successfully."
    assert response.json() == {"id": genre.id, "name": update_data["name"]}
    await db_session.refresh(genre)
    assert genre.name == update_data["name"], "Name should be updated"

@pytest.mark.asyncio
async def test_update_not_exist_genre(auth_client, db_session):
    update_data = {"name": "new_genre"}

    response = await auth_client.patch((Base_URL + f"100/"),
                                       json=update_data)
    assert response.status_code == 404, "Expected code 404,Genre with the given ID was not found"


@pytest.mark.asyncio
async def test_list_genre_success(client, db_session, seed_database):
    stmt = select(GenreModel).options(selectinload(GenreModel.movies))
    result = await db_session.execute(stmt)
    genres = result.scalars().all()
    response = await client.get(Base_URL)

    assert response.status_code == 200, "Expected code 200"
    expected = sorted(
        [{"id": genre.id, "name": genre.name, "number_of_movies": len(genre.movies)} for genre in genres],
        key=lambda x: x["id"]
    )
    actual = sorted(response.json()["genres"], key=lambda x: x["id"])
    assert expected == actual

@pytest.mark.asyncio
async def test_get_related_movies(client, db_session, seed_database):
    stmt = select(GenreModel).options(selectinload(GenreModel.movies))
    result = await db_session.execute(stmt)
    genres = result.scalars().all()
    genre = choice(genres)
    related_movies_stmt = select(MovieModel).where(MovieModel.genres.any(id=genre.id))
    result = await db_session.execute(related_movies_stmt)
    related_movies = result.scalars().all()
    expected = [MovieBaseSchema.model_validate(movie).model_dump(mode="json") for movie in related_movies]

    response = await client.get(Base_URL + f"{genre.id}/")
    assert response.status_code == 200, "Expected code 200"
    assert response.json()["movies"] == expected

@pytest.mark.asyncio
async def test_get_related_movies_with_not_exist_genre(client, db_session):

    response = await client.get(Base_URL + "1/")
    assert response.status_code == 404, "Expected code 404"

