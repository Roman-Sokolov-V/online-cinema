import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from database import MovieModel, UserModel, CommentModel
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

Base_URL = "/api/v1/opinions/movies/comment/"


async def get_movie_and_comment(user_data: dict, session: AsyncSession) -> CommentModel:
    stmt = select(MovieModel)
    result = await session.execute(stmt)
    movie = result.scalars().first()
    user_id = user_data["user"].id
    comment = CommentModel(
        content="some text", user_id=user_id, movie_id=movie.id
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return movie, comment



@pytest.mark.asyncio
async def test_create_comment_successfully(
        client, db_session, seed_database, create_activate_login_user
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    stmt = select(MovieModel)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()

    comment_data = {"content": "test content"}

    response = await client.post(
        Base_URL + f"{movie.id}/", json=comment_data, headers=header
    )
    assert response.status_code == 201, "Expected 201"
    assert response.json().get("id") is not None
    assert response.json().get("movie_id") == movie.id
    assert response.json().get("user_id") == user_data["user"].id
    assert response.json().get("content") == comment_data["content"]


@pytest.mark.asyncio
async def test_create_comment_if_already_exists(
        client, db_session, seed_database, create_activate_login_user
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    stmt = select(MovieModel)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()

    comment_data = {"content": "test content"}

    response = await client.post(
        Base_URL + f"{movie.id}/", json=comment_data, headers=header
    )
    assert response.status_code == 201, "Expected 201"

    response = await client.post(
        Base_URL + f"{movie.id}/", json=comment_data, headers=header
    )
    assert response.status_code == 400, "Expected 400"
    assert response.json()["detail"] == "You already commented this movie"


@pytest.mark.asyncio
async def test_create_comment_if_no_movie(
        client, db_session, create_activate_login_user
):
    user_data = await create_activate_login_user()
    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    comment_data = {"content": "test content"}

    response = await client.post(
        Base_URL + "1/", json=comment_data, headers=header
    )
    assert response.status_code == 404, "Expected 404"
    assert response.json()["detail"] == "Movie not found."


@pytest.mark.asyncio
async def test_create_reply_successfully(
        client, db_session, seed_database, create_activate_login_user
):
    user_data = await create_activate_login_user()
    movie, comment = await get_movie_and_comment(
        user_data=user_data, session=db_session
    )
    reply_user_data = await create_activate_login_user(prefix="another")
    reply_user = reply_user_data["user"]
    header = {"Authorization": f"Bearer {reply_user_data['access_token']}"}

    reply_data = {"content": "test content", "is_like": True}

    response = await client.post(
        Base_URL + f"reply/{comment.id}/", json=reply_data, headers=header
    )
    print(response.json())
    assert response.status_code == 201, "Expected 201"
    assert response.json().get("id") is not None
    assert response.json().get("content") == reply_data["content"]
    assert response.json().get("is_like") == reply_data["is_like"]
    assert response.json().get("user_id") == reply_user.id
    assert response.json().get("movie_id") == movie.id
    assert response.json().get("parent_id") == comment.id



@pytest.mark.asyncio
async def test_create_reply_to_own_comment(
        client, db_session, seed_database, create_activate_login_user
):
    user_data = await create_activate_login_user()
    movie, comment = await get_movie_and_comment(
        user_data=user_data, session=db_session
    )

    header = {"Authorization": f"Bearer {user_data['access_token']}"}
    reply_data = {"content": "test content"}

    response = await client.post(
        Base_URL + f"reply/{comment.id}/", json=reply_data, headers=header
    )
    assert response.status_code == 400, "Expected 400"
    assert response.json()["detail"] == "You can't reply your commentary."

    await db_session.refresh(comment)
    assert comment.replies == []


@pytest.mark.asyncio
async def test_create_reply_with_no_content_no_likes(
        client, db_session, seed_database, create_activate_login_user
):
    user_data = await create_activate_login_user()
    movie, comment = await get_movie_and_comment(
        user_data=user_data, session=db_session
    )
    reply_user_data = await create_activate_login_user(prefix="another")
    reply_user = reply_user_data["user"]
    header = {"Authorization": f"Bearer {reply_user_data['access_token']}"}

    reply_data = {}

    response = await client.post(
        Base_URL + f"reply/{comment.id}/", json=reply_data, headers=header
    )
    assert response.status_code == 422, "Expected 422"
    error_msgs = [err["msg"] for err in response.json()["detail"]]
    assert "Value error, At least one of content or is_like must be set" in error_msgs
