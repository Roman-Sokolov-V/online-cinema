import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import get_settings, get_accounts_email_notificator, \
    get_s3_storage_client
from database import (
    reset_database,
    get_db_contextmanager,
    UserGroupEnum,
    UserGroupModel, RefreshTokenModel
)
from database.populate import CSVDatabaseSeeder
from main import app
from security.interfaces import JWTAuthManagerInterface
from security.token_manager import JWTAuthManager
from storages import S3StorageClient
from tests.doubles.fakes.storage import FakeS3Storage
from tests.doubles.stubs.emails import StubEmailSender

from database import UserModel


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests"
    )
    config.addinivalue_line(
        "markers", "order: Specify the order of test execution"
    )
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_db(request):
    """
    Reset the SQLite database before each test function, except for tests marked with 'e2e'.

    By default, this fixture ensures that the database is cleared and recreated before every
    test function to maintain test isolation. However, if the test is marked with 'e2e',
    the database reset is skipped to allow preserving state between end-to-end tests.
    """
    if "e2e" in request.keywords:
        yield
    else:
        await reset_database()
        yield


@pytest_asyncio.fixture(scope="session")
async def reset_db_once_for_e2e(request):
    """
    Reset the database once for end-to-end tests.

    This fixture is intended to be used for end-to-end tests at the session scope,
    ensuring the database is reset before running E2E tests.
    """
    await reset_database()


@pytest_asyncio.fixture(scope="session")
async def settings():
    """
    Provide application settings.

    This fixture returns the application settings by calling get_settings().
    """
    return get_settings()


@pytest_asyncio.fixture(scope="function")
async def email_sender_stub():
    """
    Provide a stub implementation of the email sender.

    This fixture returns an instance of StubEmailSender for testing purposes.
    """
    return StubEmailSender()


@pytest_asyncio.fixture(scope="function")
async def s3_storage_fake():
    """
    Provide a fake S3 storage client.

    This fixture returns an instance of FakeS3Storage for testing purposes.
    """
    return FakeS3Storage()


@pytest_asyncio.fixture(scope="session")
async def s3_client(settings):
    """
    Provide an S3 storage client.

    This fixture returns an instance of S3StorageClient configured with the application settings.
    """
    return S3StorageClient(
        endpoint_url=settings.S3_STORAGE_ENDPOINT,
        access_key=settings.S3_STORAGE_ACCESS_KEY,
        secret_key=settings.S3_STORAGE_SECRET_KEY,
        bucket_name=settings.S3_BUCKET_NAME
    )


@pytest_asyncio.fixture(scope="function")
async def client(email_sender_stub, s3_storage_fake):
    """
    Provide an asynchronous HTTP client for testing.

    Overrides the dependencies for email sender and S3 storage with test doubles.
    """
    app.dependency_overrides[
        get_accounts_email_notificator] = lambda: email_sender_stub
    app.dependency_overrides[get_s3_storage_client] = lambda: s3_storage_fake

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="session")
async def e2e_client():
    """
    Provide an asynchronous HTTP client for end-to-end tests.

    This client is available at the session scope.
    """
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Provide an async database session for database interactions.

    This fixture yields an async session using `get_db_contextmanager`, ensuring that the session
    is properly closed after each test.
    """
    async with get_db_contextmanager() as session:
        yield session


@pytest_asyncio.fixture(scope="session")
async def e2e_db_session():
    """
    Provide an async database session for end-to-end tests.

    This fixture yields an async session using `get_db_contextmanager` at the session scope,
    ensuring that the same session is used throughout the E2E test suite.
    Note: Using a session-scoped DB session in async tests may lead to shared state between tests,
    so use this fixture with caution if tests run concurrently.
    """
    async with get_db_contextmanager() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def jwt_manager() -> JWTAuthManagerInterface:
    """
    Asynchronous fixture to create a JWT authentication manager instance.

    This fixture retrieves the application settings via `get_settings()` and uses them to
    instantiate a `JWTAuthManager`. The manager is configured with the secret keys for
    access and refresh tokens, as well as the JWT signing algorithm specified in the settings.

    Returns:
        JWTAuthManagerInterface: An instance of JWTAuthManager configured with the appropriate
        secret keys and algorithm.
    """
    settings = get_settings()
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )


@pytest_asyncio.fixture(scope="function")
async def seed_user_groups(db_session: AsyncSession):
    """
    Asynchronously seed the UserGroupModel table with default user groups.

    This fixture inserts all user groups defined in UserGroupEnum into the database and commits the transaction.
    It then yields the asynchronous database session for further testing.
    """
    groups = [{"name": group.value} for group in UserGroupEnum]
    await db_session.execute(insert(UserGroupModel).values(groups))
    await db_session.commit()
    yield db_session


@pytest_asyncio.fixture(scope="function")
async def seed_database(db_session):
    """
    Seed the database with test data if it is empty.

    This fixture initializes a `CSVDatabaseSeeder` and ensures the test database is populated before
    running tests that require existing data.

    :param db_session: The async database session fixture.
    :type db_session: AsyncSession
    """
    settings = get_settings()
    seeder = CSVDatabaseSeeder(csv_file_path=settings.PATH_TO_MOVIES_CSV,
                               db_session=db_session)

    if not await seeder.is_db_populated():
        await seeder.seed()

    yield db_session


@pytest_asyncio.fixture
async def register_user(client, db_session, seed_user_groups):
    """
    Фабрика для реєстрації користувача.

    Повертає функцію, яка приймає registration_payload і створює користувача.
    """

    async def _create_user(
            registration_payload: dict = {
                "email": "testuser@example.com",
                "password": "StrongPassword123!"
            }
    ):
        registration_response = await client.post("/api/v1/accounts/register/",
                                                  json=registration_payload)
        assert registration_response.status_code == 201
        stmt = (
            select(UserModel)
            .options(joinedload(UserModel.activation_token))
            .where(UserModel.email == registration_payload["email"])
        )
        result = await db_session.execute(stmt)
        user = result.scalars().first()

        activation_payload = {
            "email": registration_payload["email"],
            "token": user.activation_token.token
        }
        return activation_payload, user

    return _create_user


@pytest_asyncio.fixture
async def create_and_login_user(client, db_session, seed_user_groups,
                                register_user):
    """
    Реєструє адміністратора, активує його обліковий запис,
    додає до групи 'admin' та повертає access_token і об'єкт користувача.

    :returns: Tuple (access_token: str, admin: UserModel)
    """

    async def _login_user(group_name: str = "user"):
        registration_payload = {
            "email": f"{group_name}@example.com",
            "password": "StrongPassword123!"
        }

        activation_payload, user = await register_user(registration_payload)

        # Активуємо користувача вручну
        user.is_active = True

        # Знаходимо групу
        stmt = select(UserGroupModel.id).where(
            UserGroupModel.name == group_name)
        result = await db_session.execute(stmt)
        id_group = result.scalars().first()

        assert id_group is not None, "Admin group must exist in the database."

        # Призначаємо користувачу групу "admin"
        user.group_id = id_group

        await db_session.commit()
        await db_session.refresh(user)
        # Логінимось
        login_response = await client.post("/api/v1/accounts/login/",
                                           json=registration_payload)
        assert login_response.status_code == 201, "Expected status code 201 for successful login."

        # Отримуємо токен
        data = login_response.json()
        access_token = data["access_token"]

        return access_token, user

    return _login_user


@pytest_asyncio.fixture
async def activate_and_login_user(client, db_session, seed_user_groups):
    """
    Registers the user, activates it, login and returns Access/Refresh tokens.
    """
    payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }

    # Register
    response = await client.post("/api/v1/accounts/register/", json=payload)
    assert response.status_code == 201

    # Activate
    stmt = select(UserModel).where(UserModel.email == payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    user.is_active = True
    await db_session.commit()

    # Login
    response = await client.post("/api/v1/accounts/login/", json=payload)
    assert response.status_code == 201
    data = response.json()
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # Check refresh_token in db
    stmt = select(RefreshTokenModel).where(
        RefreshTokenModel.user_id == user.id)
    result = await db_session.execute(stmt)
    db_refresh_token = result.scalars().first()
    assert db_refresh_token.token == refresh_token

    return {
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "payload": payload,
    }


@pytest_asyncio.fixture
def jwt_manager() -> JWTAuthManagerInterface:
    settings = get_settings()
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )
