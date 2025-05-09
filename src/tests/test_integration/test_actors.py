import random
from http import HTTPStatus
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload, selectinload

from database import MovieModel, CertificationModel
from database import StarModel
from routes.permissions import is_moderator_or_admin
from sqlalchemy import insert

Base_URL = "/api/v1/theater/actors/"


@pytest.fixture(scope="function")
async def create_actor(db_session):
    stmt = insert(StarModel).values(
        [
            {"name": "Leonardo DiCaprio"},
            {"name": "Tom Hanks"},
            {"name": "Denzel Washington"},
        ]
    )
    await db_session.execute(stmt)
    await db_session.commit()
    stmt = select(StarModel)
    result = await db_session.execute(stmt)
    actors = result.scalars().all()
    return actors


@pytest.mark.asyncio
async def test_permission(client, db_session, create_activate_login_user):
    user_data = await create_activate_login_user(group_name="user")
    user_header = {"Authorization": f"Bearer {user_data['access_token']}"}

    admin_data = await create_activate_login_user(group_name="admin")
    admin_header = {"Authorization": f"Bearer {admin_data['access_token']}"}

    moderator_data = await create_activate_login_user(group_name="moderator")
    moderator_header = {
        "Authorization": f"Bearer {moderator_data['access_token']}"}

    response = await client.post(
        Base_URL, json={"name": "Brad Pitt"}, headers=user_header
    )
    assert response.status_code == 403, "User does not have enough permissions"

    response = await client.post(Base_URL, json={"name": "Johnny Depp"},
                                 headers=admin_header)
    assert response.status_code != 403, "Admin should has permissions, to create actor"
    assert response.status_code == 201, "Expected code 201, if create actor successful"

    response = await client.post(Base_URL, json={"name": "Morgan Freeman"},
                                 headers=moderator_header)
    assert response.status_code != 403, "Moderator shold has permissions, to create a actor"
    assert response.status_code == 201, "Expected code 201, if create actor successful"

    stmt = select(StarModel.id)
    result = await db_session.execute(stmt)
    actor_ids = result.scalars().all()
    assert len(actor_ids) == 2, "Should be 2 actors in db"
    actor_id = actor_ids[0]
    actor_id_2 = actor_ids[1]

    response = await client.patch(
        f"/api/v1/theater/actors/{actor_id}/",
        json={"name": "action"}, headers=user_header
    )
    assert response.status_code == 403, "User shold not has permissions to patch actor"

    response = await client.patch(
        f"/api/v1/theater/actors/{actor_id}/",
        json={"name": "comedy"}, headers=admin_header
    )
    assert response.status_code != 403, "Admin shold has permissions, to patch actor"
    assert response.status_code == 200, "Expected code 200, if patch successful"

    response = await client.patch(
        f"/api/v1/theater/actors/{actor_id}/",
        json={"name": "horror"}, headers=moderator_header
    )
    assert response.status_code != 403, "Moderator shold has permissions, to patch actor"
    assert response.status_code == 200, "Expected code 200, if patch successful"

    response = await client.patch(
        f"/api/v1/theater/actors/{actor_id}/",
        json={"name": "action"}, headers=user_header
    )
    assert response.status_code == 403, "User shold not have permissions to patch actor"

    response = await client.patch(
        f"/api/v1/theater/actors/{actor_id}/",
        json={"name": "comedy"}, headers=admin_header
    )
    assert response.status_code != 403, "Admin shold has permissions, to patch actor"
    assert response.status_code == 200, "Expected code 200, if patch successful"

    response = await client.patch(
        f"/api/v1/theater/actors/{actor_id}/",
        json={"name": "horror"}, headers=moderator_header
    )
    assert response.status_code != 403, "Moderator shold has permissions, to patch actor"
    assert response.status_code == 200, "Expected code 200, if patch successful"


@pytest.mark.asyncio
async def test_actor_create_successfully(auth_client, db_session):
    create_data = {"name": "new_actor"}
    response = await auth_client.post(Base_URL, json=create_data)
    assert response.status_code == 201, "Expected 201 Created"
    stmt = select(StarModel).where(StarModel.name == "new_actor")
    result = await db_session.execute(stmt)
    actor_db = result.scalars().first()
    assert actor_db is not None, "Actor was not created"
    assert (
            actor_db.id == response.json()["id"]
            and actor_db.name == response.json()["name"] == create_data["name"]
    ), "Response data and db data does not match"


@pytest.mark.asyncio
async def test_actor_create_with_exists_actor_name(auth_client, db_session):
    create_data = {"name": "new_actor"}
    response = await auth_client.post(Base_URL, json=create_data)
    assert response.status_code == 201, "Expected 201 Created"

    stmt = select(StarModel).where(StarModel.name == "new_actor")
    result = await db_session.execute(stmt)
    exists_actor_db = result.scalars().first()

    response = await auth_client.post(Base_URL, json=create_data)

    assert response.status_code == 409, "Expected 409 Conflict"

    stmt = select(StarModel).where(StarModel.name == "new_actor")
    result = await db_session.execute(stmt)
    actors = result.scalars().all()
    assert len(actors) == 1, "Actor-name should be unique"
    updated_actor_db = actors[0]
    assert exists_actor_db == updated_actor_db, "Exists actor, should not be deleted"


@pytest.mark.asyncio
async def test_delete_actor_success(auth_client, db_session, create_actor):
    actor, _, _ = create_actor
    response = await auth_client.delete((Base_URL + f"{actor.id}/"))
    assert response.status_code == 204, "Expected code 204, delete successfully"
    actor_db = await db_session.scalar(
        select(StarModel).where(StarModel.id == actor.id))
    assert actor_db is None, "Star should be deleted"


@pytest.mark.asyncio
async def test_delete_not_exist_actor(auth_client, db_session):
    response = await auth_client.delete((Base_URL + f"100/"))
    assert response.status_code == 404, "Expected code 404, Actor has not found"


@pytest.mark.asyncio
async def test_update_actor_success(auth_client, db_session, create_actor):
    actor, _, _ = create_actor
    update_data = {"name": "new_actor"}
    assert actor.name != update_data["name"], "Names should not be the same"
    response = await auth_client.patch((Base_URL + f"{actor.id}/"),
                                       json=update_data)
    assert response.status_code == 200, "Expected code 200, actor updated successfully."
    assert response.json() == {"id": actor.id, "name": update_data["name"]}
    await db_session.refresh(actor)
    assert actor.name == update_data["name"], "Name should be updated"

@pytest.mark.asyncio
async def test_update_not_exist_actor(auth_client, db_session):
    update_data = {"name": "new_actor"}

    response = await auth_client.patch((Base_URL + f"100/"),
                                       json=update_data)
    assert response.status_code == 404, "Expected code 404,Star with the given ID was not found"


@pytest.mark.asyncio
async def test_list_actor_success(client, db_session, create_actor):
    actors = create_actor
    response = await client.get(Base_URL)
    assert response.status_code == 200, "Expected code 200"
    expected = sorted(
        [{"id": actor.id, "name": actor.name} for actor in actors],
        key=lambda x: x["id"]
    )
    actual = sorted(response.json()["stars"], key=lambda x: x["id"])
    assert expected == actual
