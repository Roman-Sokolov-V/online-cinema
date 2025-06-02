import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from io import BytesIO
from PIL import Image

from config import get_settings, get_email_notificator, \
    get_s3_storage_client
from database import (
    reset_database,
    get_db_contextmanager,
    UserGroupEnum,
    UserGroupModel, RefreshTokenModel, UserProfileModel
)
from database.populate import CSVDatabaseSeeder
from main import app
from routes.permissions import is_moderator_or_admin
from security.interfaces import JWTAuthManagerInterface
from security.token_manager import JWTAuthManager
from storages import S3StorageClient
from tests.doubles.fakes.storage import FakeS3Storage
from tests.doubles.stubs.emails import StubEmailSender

from database import UserModel, MovieModel


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
async def override_is_moderator_or_admin():
    """
    Provide a fake is_moderator_or_admin dependency.

    This fixture returns None to imitate successfully authentication
    and authorisation.
    """
    return None

############################################################################
@pytest_asyncio.fixture(scope="function")
async def auth_client(
        email_sender_stub, s3_storage_fake, override_is_moderator_or_admin
):
    """
    Provide an asynchronous HTTP client for testing.

    Overrides the dependencies for email sender S3 storage with test doubles,
    and successfully authentication and authorisation
    """
    app.dependency_overrides[
        get_email_notificator] = lambda: email_sender_stub
    app.dependency_overrides[get_s3_storage_client] = lambda: s3_storage_fake
    app.dependency_overrides[
        is_moderator_or_admin] = lambda: override_is_moderator_or_admin

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def client(email_sender_stub, s3_storage_fake):
    """
    Provide an asynchronous HTTP client for testing.

    Overrides the dependencies for email sender and S3 storage with test doubles.
    """
    app.dependency_overrides[
        get_email_notificator] = lambda: email_sender_stub
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
    stmt = select(UserGroupModel.id)
    result = await db_session.execute(stmt)
    exists_group = result.scalars().all()
    if not exists_group:
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
async def create_activate_login_user(
        client, db_session, seed_user_groups, register_user
):
    """
    Register a user, activates his account,
    adds to a group of a certain group ("user" by default)
    and returns access_token, refresh_token, user, payload.

    :returns: dict {
        user: UserModel,
        access_token: str,
        refresh_token: str,
        payload: Dict {email: str, password: str}
    }
    """

    async def _login_user(group_name: str = "user", prefix: str = ""):
        registration_payload = {
            "email": f"{prefix}{group_name}@example.com",
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
        login_response = await client.post(
            "/api/v1/accounts/login/", json=registration_payload
        )
        assert login_response.status_code == 201, "Expected status code 201 for successful login."

        # Отримуємо токени
        data = login_response.json()
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "payload": registration_payload,
        }

    return _login_user


@pytest_asyncio.fixture
def jwt_manager() -> JWTAuthManagerInterface:
    settings = get_settings()
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )


@pytest_asyncio.fixture
async def create_user_and_profile(
        db_session, seed_user_groups, reset_db, jwt_manager, s3_storage_fake,
        client
):
    """
    Positive test for updating a user profile.

    Steps:
    1. Create a test user and activate them.
    2. Generate an access token using `jwt_manager`.
    3. Create user profile using create_profile endpoint
    return: tuple(user: UserModel, headers: dict)
    """
    user = UserModel.create(email="test@mate.com",
                            raw_password="TestPassword123!", group_id=1)
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    stmt = select(UserModel).where(UserModel.email == "test@mate.com")
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    access_token = jwt_manager.create_access_token({"user_id": user.id})
    img = Image.new("RGB", (100, 100), color="blue")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    avatar_key = f"avatars/{user.id}_avatar.jpg"
    profile_url = f"/api/v1/profiles/users/{user.id}/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {
        "first_name": (None, "John"),
        "last_name": (None, "Doe"),
        "gender": (None, "man"),
        "date_of_birth": (None, "1990-01-01"),
        "info": (None, "This is a test profile."),
        "avatar": ("avatar.jpg", img_bytes, "image/jpeg"),
    }

    response = await client.post(profile_url, headers=headers, files=files)

    expected_url = f"http://fake-s3.local/{avatar_key}"
    actual_url = await s3_storage_fake.get_file_url(avatar_key)
    stmt = select(UserProfileModel).where(UserProfileModel.user == user)
    result = await db_session.execute(stmt)
    profile = result.scalars().first()

    return user, headers, profile


@pytest_asyncio.fixture
async def get_movie(db_session):
    stmt = select(MovieModel).options(
        joinedload(MovieModel.users_like)).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    return movie


@pytest_asyncio.fixture
async def get_3_movies(db_session):
    stmt = select(MovieModel).limit(3)
    result = await db_session.execute(stmt)
    movies = result.scalars().all()
    return movies



@pytest_asyncio.fixture
async def create_orders(get_3_movies, client, create_activate_login_user):
    from tests.test_integration.test_orders import BASE_URL
    movies = get_3_movies
    prefix = 1

    # create 3 orders for 3 users with 3 movies
    users_data = dict()
    for movie in movies:
        user_data = await create_activate_login_user(prefix=str(prefix))
        user = user_data["user"]
        header = {"Authorization": f"Bearer {user_data['access_token']}"}
        users_data["user" + str(prefix)] = (user, header)

        response = await client.post(
            f"/api/v1/cart/items/{movie.id}/", headers=header)
        assert response.status_code == 200
        response = await client.post(BASE_URL + "place/", headers=header)
        assert response.status_code == 303
        prefix += 1
    return {"users_data": users_data, "movies": movies}
