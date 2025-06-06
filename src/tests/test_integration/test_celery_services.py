from datetime import datetime, timezone, timedelta
from sqlalchemy import select
import pytest

from celery_.tasks import remove_expired_activation_tokens
from database import (
    ActivationTokenModel,
    reset_sync_sqlite_database,
    get_sync_db_contextmanager, UserGroupModel, UserModel
)


@pytest.fixture(scope="function", autouse=True)
def reset_db(request):
    """
    Reset the SQLite database before each test function,
    By default, this fixture ensures that the database
    is cleared and recreated before every
    test function to maintain test isolation.
    """
    reset_sync_sqlite_database()
    yield


@pytest.fixture(scope="function")
def sync_db():
    """
    Provide an async database session for database interactions.
    This fixture yields an async session using `get_db_contextmanager`
    , ensuring that the session
    is properly closed after each test.
    """
    with get_sync_db_contextmanager() as session:
        yield session


def test_remove_expired_activation_tokens(sync_db):
    group = UserGroupModel(name="user")
    sync_db.add(group)
    sync_db.commit()
    sync_db.refresh(group)
    user_1 = UserModel.create(
        email="testuser@example.com",
        raw_password="StrongPassword123!",
        group_id=group.id
    )
    user_2 = UserModel.create(
        email="testuser2@example.com",
        raw_password="StrongPassword1234!",
        group_id=group.id
    )
    sync_db.add_all([user_1, user_2])
    sync_db.flush()

    user_1_token = ActivationTokenModel(user=user_1)
    user_2_token = ActivationTokenModel(user=user_2)

    sync_db.add_all([user_1_token, user_2_token])
    sync_db.flush()

    user_1_token.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    sync_db.commit()
    remove_expired_activation_tokens()

    stmt = select(ActivationTokenModel)
    result = sync_db.execute(stmt)
    tokens = result.scalars().all()
    assert len(tokens) == 1, "Expired activation token should be deleted"
    assert tokens[0].id == user_2_token.id, "Not expired activation token should not be deleted"
