from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select, delete, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from config import get_settings
from database import (
    UserModel,
    ActivationTokenModel,
    PasswordResetTokenModel,
    UserGroupModel,
    UserGroupEnum,
    RefreshTokenModel
)

from config import get_jwt_auth_manager


@pytest.mark.asyncio
async def test_register_user_success(client, db_session, seed_user_groups):
    """
    Test successful user registration.

    Validates that a new user and an activation token are created in the database.
    """
    payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }

    response = await client.post("/api/v1/accounts/register/", json=payload)
    assert response.status_code == 201, "Expected status code 201 Created."
    response_data = response.json()
    assert response_data["email"] == payload[
        "email"], "Returned email does not match."
    assert "id" in response_data, "Response does not contain user ID."

    stmt_user = select(UserModel).where(UserModel.email == payload["email"])
    result = await db_session.execute(stmt_user)
    created_user = result.scalars().first()
    assert created_user is not None, "User was not created in the database."
    assert created_user.email == payload[
        "email"], "Created user's email does not match."

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == created_user.id)
    result = await db_session.execute(stmt_token)
    activation_token = result.scalars().first()
    assert activation_token is not None, "Activation token was not created in the database."
    assert activation_token.user_id == created_user.id, "Activation token's user_id does not match."
    assert activation_token.token is not None, "Activation token has no token value."

    expires_at = activation_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at > datetime.now(
        timezone.utc), "Activation token is already expired."


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_password, expected_error", [
    ("short", "Password must contain at least 8 characters."),
    ("NoDigitHere!", "Password must contain at least one digit."),
    ("nodigitnorupper@",
     "Password must contain at least one uppercase letter."),
    ("NOLOWERCASE1@", "Password must contain at least one lower letter."),
    ("NoSpecial123",
     "Password must contain at least one special character: @, $, !, %, *, ?, #, &."),
])
async def test_register_user_password_validation(client, seed_user_groups,
                                                 invalid_password,
                                                 expected_error):
    """
    Test password strength validation in the user registration endpoint.

    Ensures that when an invalid password is provided, the endpoint returns the appropriate
    error message and a 422 status code.

    Args:
        client: The asynchronous HTTP client fixture.
        seed_user_groups: Fixture that seeds the default user groups.
        invalid_password (str): The password to test.
        expected_error (str): The expected error message substring.
    """
    payload = {
        "email": "testuser@example.com",
        "password": invalid_password
    }

    response = await client.post("/api/v1/accounts/register/", json=payload)
    assert response.status_code == 422, "Expected status code 422 for invalid input."

    response_data = response.json()
    assert expected_error in str(
        response_data), f"Expected error message: {expected_error}"


@pytest.mark.asyncio
async def test_register_user_conflict(client, db_session, seed_user_groups):
    """
    Test user registration conflict.

    Ensures that trying to register a user with an existing email
    returns a 409 Conflict status and the correct error message.

    Args:
        client: The asynchronous HTTP client fixture.
        db_session: The asynchronous database session fixture.
        seed_user_groups: Fixture that seeds default user groups.
    """
    payload = {
        "email": "conflictuser@example.com",
        "password": "StrongPassword123!"
    }

    response_first = await client.post("/api/v1/accounts/register/",
                                       json=payload)
    assert response_first.status_code == 201, "Expected status code 201 for the first registration."

    stmt = select(UserModel).where(UserModel.email == payload["email"])
    result = await db_session.execute(stmt)
    created_user = result.scalars().first()
    assert created_user is not None, "User should be created after the first registration."

    response_second = await client.post("/api/v1/accounts/register/",
                                        json=payload)
    assert response_second.status_code == 409, "Expected status code 409 for a duplicate registration."

    response_data = response_second.json()
    expected_message = f"A user with this email {payload['email']} already exists."
    assert response_data[
               "detail"] == expected_message, f"Expected error message: {expected_message}"


@pytest.mark.asyncio
async def test_register_user_internal_server_error(client, seed_user_groups):
    """
    Test server error during user registration.

    Ensures that a 500 Internal Server Error is returned when a database operation fails.

    This test patches the commit method of the AsyncSession to simulate a SQLAlchemyError,
    then verifies that the registration endpoint returns the appropriate HTTP 500 error
    with the expected error message.
    """
    payload = {
        "email": "erroruser@example.com",
        "password": "StrongPassword123!"
    }

    with patch("routes.accounts.AsyncSession.commit",
               side_effect=SQLAlchemyError):
        response = await client.post("/api/v1/accounts/register/",
                                     json=payload)

        assert response.status_code == 500, "Expected status code 500 for internal server error."

        response_data = response.json()
        expected_message = "An error occurred during user creation."
        assert response_data[
                   "detail"] == expected_message, f"Expected error message: {expected_message}"


@pytest.mark.asyncio
async def test_activate_account_success_with_activation_token(
        client,
        db_session,
        seed_user_groups,
        register_user
):
    """
    Test successful activation of a user account.

    Steps:
    - Register a new user.
    - Verify the user is inactive.
    - Activate the user using the activation token.
    - Verify the user is activated and the token is deleted.
    """

    activation_payload, registered_user = await register_user()
    assert registered_user.is_active is False, "User should be not active before activate"

    activation_response = await client.post("/api/v1/accounts/activate/",
                                            json=activation_payload)
    assert activation_response.status_code == 200, "Expected status code 200 for successful activation."
    assert activation_response.json()[
               "detail"] == "User account activated successfully."

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.activation_token))
        .where(UserModel.email == activation_payload["email"])
    )
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    await db_session.refresh(user)
    assert user.is_active, "User should be active after successful activation."

    stmt = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id)
    result = await db_session.execute(stmt)
    token = result.scalars().first()
    assert token is None, "Activation token should be deleted after successful activation."


@pytest.mark.asyncio
async def test_activate_account_success_with_admin_access_token(
        client,
        db_session,
        seed_user_groups,
        register_user,
        create_activate_login_user
):
    """
    Test successful activation of a user account.

    Steps:
    - Register an admin-user
    - Register a new user.
    - Verify the user is inactive.
    - Activate the user using the admin access token
    - Verify the user is activated and the token is deleted.
    """

    logged_user_data = await create_activate_login_user(group_name="admin")
    activation_payload, user = await register_user()
    activation_payload.pop("token")
    assert user.is_active is False, "User should be not active before activate"

    response = await client.post(
        "/api/v1/accounts/activate/",
        json=activation_payload,
        headers={
            "Authorization": f"Bearer {logged_user_data["access_token"]}"
        }
    )

    assert response.status_code == 200, "Expected status code 200 for successful activation."
    assert response.json()["detail"] == "User account activated successfully."

    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.activation_token))
        .where(UserModel.email == activation_payload["email"])
    )
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    await db_session.refresh(user)
    assert user.is_active, "User should be active after successful activation."

    stmt = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id)
    result = await db_session.execute(stmt)
    token = result.scalars().first()
    assert token is None, "Activation token should be deleted after successful activation."


@pytest.mark.asyncio
async def test_activate_account_with_not_admin_access_token(
        client,
        db_session,
        seed_user_groups,
        register_user,
        create_activate_login_user
):
    """
    Test unsuccessful activation of a user account.

    Steps:
    - Register and login request user in group - 'user'
    - Register a new user.
    - Verify the user is inactive.
    - Try to activate the user using user access token
    - Verify the user is not activated and the token is not deleted.
    - Change request user`s group as group - 'moderator'
    - Try to activate the user using moderator access token
    - Verify the user is not activated and the token is not deleted.
    """

    logged_user_data = await create_activate_login_user(group_name="user")
    activation_payload, user = await register_user()

    activation_payload.pop("token")
    assert user.is_active is False, "User should be not active before activate"

    response = await client.post(
        "/api/v1/accounts/activate/",
        json=activation_payload,
        headers={
            "Authorization": f"Bearer {logged_user_data["access_token"]}"
        }
    )

    assert response.status_code == 403, "Expected status code 403, not admin users don`t have permission to activate account by access token"
    await db_session.refresh(user)
    assert user.is_active is False, "User should not be active after unsuccessful activation."
    stmt = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id)
    result = await db_session.execute(stmt)
    token = result.scalars().first()
    assert token is not None, "Activation token should not be deleted after unsuccessful activation."

    stmt = select(UserGroupModel.id).filter_by(name="moderator")
    result = await db_session.execute(stmt)
    group_id_moderator = result.scalars().first()
    assert group_id_moderator is not None
    logged_user_data["user"].group_id = group_id_moderator
    await db_session.commit()
    response = await client.post(
        "/api/v1/accounts/activate/",
        json=activation_payload,
        headers={
            "Authorization": f"Bearer {logged_user_data["access_token"]}"
        }
    )
    assert response.status_code == 403, "Expected status code 403, not admin users don`t have permission to activate account by access token"
    await db_session.refresh(user)
    assert user.is_active is False, "User should not be active after unsuccessful activation."
    stmt = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id)
    result = await db_session.execute(stmt)
    token = result.scalars().first()
    assert token is not None, "Activation token should not be deleted after unsuccessful activation."


@pytest.mark.asyncio
async def test_activate_account_with_expired_admin_access_token(
        client,
        db_session,
        seed_user_groups,
        register_user,
        create_activate_login_user
):
    """
    Test unsuccessful activation of a user account.

    Steps:
    - Register and login request user in group - 'admin'
    - Manually create expired access token
    - Register a new user.
    - Verify the user is inactive.
    - Try to activate the user using expired admin access token
    - Verify the user is not activated and the token is not deleted.
    """

    logged_user_data = await create_activate_login_user(group_name="admin")
    expires_delta = timedelta(minutes=-3000)
    settings = get_settings()
    manager = get_jwt_auth_manager(settings=settings)
    access_token = manager.create_access_token(
        {"user_id": logged_user_data["user"].id}, expires_delta=expires_delta
    )

    activation_payload, user = await register_user()

    activation_payload.pop("token")
    assert user.is_active is False, "User should be not active before activate"

    response = await client.post(
        "/api/v1/accounts/activate/",
        json=activation_payload,
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )
    assert response.status_code == 401, "Expected status code 401, if access token expired"
    await db_session.refresh(user)
    assert user.is_active is False, "User should not be active after unsuccessful activation."
    token = await db_session.scalar(
        select(ActivationTokenModel)
        .where(ActivationTokenModel.user_id == user.id)
    )
    assert token is not None, "Activation token should not be deleted after unsuccessful activation."


@pytest.mark.asyncio
async def test_activate_user_with_expired_token(client, db_session,
                                                seed_user_groups):
    """
    Test activation with an expired token.

    Ensures that the endpoint returns a 400 error when the activation token is expired.
    Steps:
    - Register a new user.
    - Retrieve the user and their activation token.
    - Manually set the token's expiration to a past date.
    - Attempt to activate the account with the expired token.
    - Verify that the response is a 400 error with the expected error message.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }
    registration_response = await client.post("/api/v1/accounts/register/",
                                              json=registration_payload)
    assert registration_response.status_code == 201, "Expected status code 201 for successful registration."

    stmt = select(UserModel).where(
        UserModel.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."
    assert not user.is_active, "User should not be active before activation."

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id)
    result_token = await db_session.execute(stmt_token)
    activation_token = result_token.scalars().first()
    assert activation_token is not None, "Activation token should exist for the user."

    activation_token.expires_at = datetime.now(timezone.utc) - timedelta(
        days=2)
    await db_session.commit()

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token
    }
    activation_response = await client.post("/api/v1/accounts/activate/",
                                            json=activation_payload)

    assert activation_response.status_code == 400, "Expected status code 400 for expired token."
    assert activation_response.json()[
               "detail"] == "Invalid or expired activation token.", (
        "Expected error message for expired token."
    )


@pytest.mark.asyncio
async def test_activate_user_with_deleted_token(client, db_session,
                                                seed_user_groups):
    """
    Test activation with a deleted token.

    Ensures that the endpoint returns a 400 error when the activation token has been deleted.

    Steps:
    - Register a new user.
    - Verify that the user is created and inactive.
    - Delete the activation token from the database.
    - Attempt to activate the account using the deleted token.
    - Verify that a 400 error is returned with the appropriate error message.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }
    registration_response = await client.post("/api/v1/accounts/register/",
                                              json=registration_payload)
    assert registration_response.status_code == 201, "Expected status code 201 for successful registration."

    stmt = select(UserModel).where(
        UserModel.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."
    assert not user.is_active, "User should not be active before activation."

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id)
    result_token = await db_session.execute(stmt_token)
    activation_token = result_token.scalars().first()
    assert activation_token is not None, "Activation token should exist for the user."

    token_value = activation_token.token

    await db_session.execute(
        delete(ActivationTokenModel).where(
            ActivationTokenModel.id == activation_token.id)
    )
    await db_session.commit()

    activation_payload = {
        "email": registration_payload["email"],
        "token": token_value
    }
    activation_response = await client.post("/api/v1/accounts/activate/",
                                            json=activation_payload)

    assert activation_response.status_code == 400, "Expected status code 400 for deleted token."
    assert activation_response.json()[
               "detail"] == "Invalid or expired activation token.", (
        "Expected error message for deleted token."
    )


@pytest.mark.asyncio
async def test_activate_already_active_user(client, db_session,
                                            seed_user_groups):
    """
    Test activation of an already active user.

    Ensures that the endpoint returns a 400 error if the user is already active.
    Steps:
    - Register a new user.
    - Mark the user as active in the database.
    - Attempt to activate the user using the activation token.
    - Verify that a 400 error with the expected error message is returned.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }

    registration_response = await client.post("/api/v1/accounts/register/",
                                              json=registration_payload)
    assert registration_response.status_code == 201, "Expected status code 201 for successful registration."

    stmt = select(UserModel).where(
        UserModel.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == user.id)
    result_token = await db_session.execute(stmt_token)
    activation_token = result_token.scalars().first()
    assert activation_token is not None, "Activation token should exist for the user."

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token
    }
    activation_response = await client.post("/api/v1/accounts/activate/",
                                            json=activation_payload)

    assert activation_response.status_code == 400, "Expected status code 400 for already active user."
    assert activation_response.json()[
               "detail"] == "User account is already active.", (
        "Expected error message for already active user."
    )


@pytest.mark.asyncio
async def test_request_password_reset_token_success(client, db_session,
                                                    seed_user_groups):
    """
    Test successful password reset token request.

    Ensures that a password reset token is created for an active user.

    Steps:
    - Register a new user.
    - Mark the user as active.
    - Request a password reset token.
    - Verify that the endpoint returns status 200 and the expected success message.
    - Query the database to confirm that a PasswordResetTokenModel record was created.
    - Verify that the token's expiration date is in the future.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }
    registration_response = await client.post("/api/v1/accounts/register/",
                                              json=registration_payload)
    assert registration_response.status_code == 201, "Expected status code 201 for successful registration."

    stmt = select(UserModel).where(
        UserModel.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    reset_payload = {"email": registration_payload["email"]}
    reset_response = await client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_payload)
    assert reset_response.status_code == 200, "Expected status code 200 for successful token request."
    assert reset_response.json()[
               "detail"] == "If you are registered, you will receive an email with instructions.", \
        "Expected success message for password reset token request."

    stmt_token = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id)
    result_token = await db_session.execute(stmt_token)
    reset_token = result_token.scalars().first()
    assert reset_token is not None, "Password reset token should be created for the user."

    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at > datetime.now(
        timezone.utc), "Password reset token should have a future expiration date."


@pytest.mark.asyncio
async def test_request_password_reset_token_nonexistent_user(client,
                                                             db_session):
    """
    Test password reset token request for a non-existent user.

    Ensures that the endpoint responds with a generic success message and that no password reset token is created
    when the email does not exist in the database.
    """
    reset_payload = {"email": "nonexistent@example.com"}

    reset_response = await client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_payload)
    assert reset_response.status_code == 200, "Expected status code 200 for non-existent user request."
    assert reset_response.json()[
               "detail"] == "If you are registered, you will receive an email with instructions.", (
        "Expected generic success message for non-existent user request."
    )

    stmt = select(func.count(PasswordResetTokenModel.id))
    result = await db_session.execute(stmt)
    reset_token_count = result.scalar_one()
    assert reset_token_count == 0, "No password reset token should be created for non-existent user."


@pytest.mark.asyncio
async def test_request_password_reset_token_for_inactive_user(client,
                                                              db_session,
                                                              seed_user_groups):
    """
    Test password reset token request for a registered but inactive user.

    Ensures that the endpoint returns the generic success message and that no password reset token
    is created when the user is registered but inactive.
    """
    registration_payload = {
        "email": "inactiveuser@example.com",
        "password": "StrongPassword123!"
    }
    registration_response = await client.post("/api/v1/accounts/register/",
                                              json=registration_payload)
    assert registration_response.status_code == 201, "Expected status code 201 for successful registration."

    stmt = select(UserModel).where(
        UserModel.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    created_user = result.scalars().first()
    assert created_user is not None, "User should be created in the database."
    assert not created_user.is_active, "User should not be active after registration."

    reset_payload = {"email": registration_payload["email"]}
    reset_response = await client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_payload)
    assert reset_response.status_code == 200, "Expected status code 200 for inactive user password reset request."
    assert reset_response.json()[
               "detail"] == "If you are registered, you will receive an email with instructions.", (
        "Expected generic success message for inactive user password reset request."
    )

    stmt_tokens = select(func.count(PasswordResetTokenModel.id))
    result_tokens = await db_session.execute(stmt_tokens)
    reset_token_count = result_tokens.scalar_one()
    assert reset_token_count == 0, "No password reset token should be created for an inactive user."


@pytest.mark.asyncio
async def test_reset_password_success(client, db_session, seed_user_groups):
    """
    Test the complete password reset flow.

    Steps:
    - Register a user.
    - Activate the user.
    - Request a password reset token.
    - Use the token to reset the password.
    - Verify the password is updated in the database.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "OldPassword123!"
    }
    registration_response = await client.post("/api/v1/accounts/register/",
                                              json=registration_payload)
    assert registration_response.status_code == 201, "Expected status code 201 for successful registration."

    stmt = select(UserModel).where(
        UserModel.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    created_user = result.scalars().first()
    assert created_user is not None, "User should be created in the database."

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == created_user.id)
    result_token = await db_session.execute(stmt_token)
    activation_token = result_token.scalars().first()
    assert activation_token is not None, "Activation token should be created in the database."

    activation_payload = {
        "email": registration_payload["email"],
        "token": activation_token.token
    }
    activation_response = await client.post("/api/v1/accounts/activate/",
                                            json=activation_payload)

    assert activation_response.status_code == 200, "Expected status code 200 for successful activation."

    await db_session.refresh(created_user)
    assert created_user.is_active, "User should be active after successful activation."

    reset_request_payload = {"email": registration_payload["email"]}
    reset_request_response = await client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_request_payload)
    assert reset_request_response.status_code == 200, "Expected status code 200 for password reset token request."

    stmt_reset = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == created_user.id)
    result_reset = await db_session.execute(stmt_reset)
    reset_token_record = result_reset.scalars().first()
    assert reset_token_record is not None, "Password reset token should be created in the database."

    new_password = "NewSecurePassword123!"
    reset_payload = {
        "email": registration_payload["email"],
        "token": reset_token_record.token,
        "password": new_password
    }
    reset_response = await client.post(
        "/api/v1/accounts/reset-password/complete/", json=reset_payload)
    assert reset_response.status_code == 200, "Expected status code 200 for successful password reset."
    assert reset_response.json()[
               "detail"] == "Password reset successfully.", (
        "Unexpected response message for password reset."
    )

    await db_session.refresh(created_user)
    assert created_user.verify_password(
        new_password), "Password should be updated successfully in the database."


@pytest.mark.asyncio
async def test_reset_password_invalid_email(client, db_session):
    """
    Test password reset with an email that does not exist in the database.

    Validates that the endpoint returns a 400 status code and appropriate error message.
    """
    reset_payload = {
        "email": "nonexistent@example.com",
        "token": "random_token",
        "password": "NewSecurePassword123!"
    }

    response = await client.post("/api/v1/accounts/reset-password/complete/",
                                 json=reset_payload)

    assert response.status_code == 400, "Expected status code 400 for invalid email."
    assert response.json()[
               "detail"] == "Invalid email or token.", "Unexpected error message."


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client, db_session,
                                            seed_user_groups):
    """
    Test password reset with an incorrect token.

    Validates that the endpoint returns a 400 status code and an appropriate error message when an invalid token is provided.
    Also ensures that any invalid token is removed from the database.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }
    response = await client.post("/api/v1/accounts/register/",
                                 json=registration_payload)
    assert response.status_code == 201, "User registration failed."

    stmt = select(UserModel).where(
        UserModel.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    reset_request_payload = {"email": registration_payload["email"]}
    response = await client.post("/api/v1/accounts/password-reset/request/",
                                 json=reset_request_payload)
    assert response.status_code == 200, "Password reset request failed."

    reset_complete_payload = {
        "email": registration_payload["email"],
        "token": "incorrect_token",
        "password": "NewSecurePassword123!"
    }
    response = await client.post("/api/v1/accounts/reset-password/complete/",
                                 json=reset_complete_payload)
    assert response.status_code == 400, "Expected status code 400 for invalid token."
    assert response.json()[
               "detail"] == "Invalid email or token.", "Unexpected error message."

    stmt_token = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id)
    result_token = await db_session.execute(stmt_token)
    token_record = result_token.scalars().first()
    assert token_record is None, "Invalid token was not removed."


@pytest.mark.asyncio
async def test_reset_password_expired_token(client, db_session,
                                            seed_user_groups):
    """
    Test password reset with an expired token.

    Validates that the endpoint returns a 400 status code and an appropriate error message when the password
    reset token is expired, and verifies that the expired token is removed from the database.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }
    registration_response = await client.post("/api/v1/accounts/register/",
                                              json=registration_payload)
    assert registration_response.status_code == 201, "User registration failed."

    stmt = select(UserModel).where(
        UserModel.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    reset_request_payload = {"email": registration_payload["email"]}
    reset_request_response = await client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_request_payload)
    assert reset_request_response.status_code == 200, "Password reset request failed."

    stmt_token = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id)
    result_token = await db_session.execute(stmt_token)
    token_record = result_token.scalars().first()
    assert token_record is not None, "Password reset token not created."

    token_record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()

    reset_complete_payload = {
        "email": registration_payload["email"],
        "token": token_record.token,
        "password": "NewSecurePassword123!"
    }
    reset_response = await client.post(
        "/api/v1/accounts/reset-password/complete/",
        json=reset_complete_payload)
    assert reset_response.status_code == 400, "Expected status code 400 for expired token."
    assert reset_response.json()[
               "detail"] == "Invalid email or token.", "Unexpected error message."

    stmt_token_check = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id)
    result_token_check = await db_session.execute(stmt_token_check)
    expired_token = result_token_check.scalars().first()
    assert expired_token is None, "Expired token was not removed."


@pytest.mark.asyncio
async def test_reset_password_sqlalchemy_error(client, db_session,
                                               seed_user_groups):
    """
    Test password reset when a database commit raises SQLAlchemyError.

    Validates that the endpoint returns a 500 Internal Server Error and the appropriate error message
    when an error occurs during the password reset process.

    Steps:
    - Register a new user.
    - Mark the user as active.
    - Request a password reset token.
    - Attempt to reset the password while simulating a database commit error.
    - Verify that a 500 error is returned with the expected error message.
    """
    registration_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }
    registration_response = await client.post("/api/v1/accounts/register/",
                                              json=registration_payload)
    assert registration_response.status_code == 201, "User registration failed."

    stmt = select(UserModel).where(
        UserModel.email == registration_payload["email"])
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    assert user is not None, "User should exist in the database."

    user.is_active = True
    await db_session.commit()

    reset_request_payload = {"email": registration_payload["email"]}
    reset_request_response = await client.post(
        "/api/v1/accounts/password-reset/request/", json=reset_request_payload)
    assert reset_request_response.status_code == 200, "Password reset request failed."

    stmt_token = select(PasswordResetTokenModel).where(
        PasswordResetTokenModel.user_id == user.id)
    result_token = await db_session.execute(stmt_token)
    token_record = result_token.scalars().first()
    assert token_record is not None, "Password reset token not created."

    reset_complete_payload = {
        "email": registration_payload["email"],
        "token": token_record.token,
        "password": "NewSecurePassword123!"
    }

    with patch("routes.accounts.AsyncSession.commit",
               side_effect=SQLAlchemyError):
        reset_response = await client.post(
            "/api/v1/accounts/reset-password/complete/",
            json=reset_complete_payload)

    assert reset_response.status_code == 500, "Expected status code 500 for SQLAlchemyError."
    assert reset_response.json()[
               "detail"] == "An error occurred while resetting the password.", (
        "Unexpected error message for SQLAlchemyError."
    )


@pytest.mark.asyncio
async def test_login_user_success(client, db_session, jwt_manager,
                                  seed_user_groups):
    """
    Test successful login.

    Validates that access and refresh tokens are returned, the refresh token is stored in the database,
    and both tokens are valid.
    """
    user_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }

    stmt = select(UserGroupModel).where(
        UserGroupModel.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"]
    }
    response = await client.post("/api/v1/accounts/login/", json=login_payload)
    assert response.status_code == 201, "Expected status code 201 for successful login."
    response_data = response.json()
    assert "access_token" in response_data, "Access token is missing in the response."
    assert "refresh_token" in response_data, "Refresh token is missing in the response."
    assert response_data["access_token"], "Access token is empty."
    assert response_data["refresh_token"], "Refresh token is empty."

    access_token_data = jwt_manager.decode_access_token(
        response_data["access_token"])
    assert access_token_data[
               "user_id"] == user.id, "Access token does not contain correct user ID."

    refresh_token_data = jwt_manager.decode_refresh_token(
        response_data["refresh_token"])
    assert refresh_token_data[
               "user_id"] == user.id, "Refresh token does not contain correct user ID."

    stmt_refresh = select(RefreshTokenModel).where(
        RefreshTokenModel.user_id == user.id)
    result_refresh = await db_session.execute(stmt_refresh)
    refresh_token_record = result_refresh.scalars().first()
    assert refresh_token_record is not None, "Refresh token was not stored in the database."
    assert refresh_token_record.token == response_data[
        "refresh_token"], "Stored refresh token does not match."

    expires_at = refresh_token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at > datetime.now(
        timezone.utc), "Refresh token is already expired."


@pytest.mark.asyncio
async def test_login_user_invalid_cases(client, db_session, seed_user_groups):
    """
    Test login with invalid cases:
    1. Non-existent user.
    2. Incorrect password for an existing user.
    """
    login_payload = {
        "email": "nonexistent@example.com",
        "password": "SomePassword123!"
    }
    response = await client.post("/api/v1/accounts/login/", json=login_payload)
    assert response.status_code == 401, "Expected status code 401 for non-existent user."
    assert response.json()["detail"] == "Invalid email or password.", \
        "Unexpected error message for non-existent user."

    user_payload = {
        "email": "testuser@example.com",
        "password": "CorrectPassword123!"
    }
    stmt = select(UserGroupModel).where(
        UserGroupModel.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload_incorrect_password = {
        "email": user_payload["email"],
        "password": "WrongPassword123!"
    }
    response = await client.post("/api/v1/accounts/login/",
                                 json=login_payload_incorrect_password)
    assert response.status_code == 401, "Expected status code 401 for incorrect password."
    assert response.json()["detail"] == "Invalid email or password.", \
        "Unexpected error message for incorrect password."


@pytest.mark.asyncio
async def test_login_user_inactive_account(client, db_session,
                                           seed_user_groups):
    """
    Test login with an inactive user account.

    Validates that the endpoint returns a 403 status code and an appropriate error message
    when attempting to log in with a user whose account is not activated.
    """
    user_payload = {
        "email": "inactiveuser@example.com",
        "password": "StrongPassword123!"
    }

    stmt = select(UserGroupModel).where(
        UserGroupModel.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "User group not found."

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id
    )
    user.is_active = False
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"]
    }
    response = await client.post("/api/v1/accounts/login/", json=login_payload)

    assert response.status_code == 403, "Expected status code 403 for inactive user."
    assert response.json()["detail"] == "User account is not activated.", \
        "Unexpected error message for inactive user."


@pytest.mark.asyncio
async def test_login_user_commit_error(client, db_session, seed_user_groups):
    """
    Test login when a database commit error occurs.

    Validates that the endpoint returns a 500 status code and an appropriate error message.
    """
    user_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }
    stmt = select(UserGroupModel).where(
        UserGroupModel.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"]
    }

    with patch("routes.accounts.AsyncSession.commit",
               side_effect=SQLAlchemyError):
        response = await client.post("/api/v1/accounts/login/",
                                     json=login_payload)

    assert response.status_code == 500, "Expected status code 500 for database commit error."
    assert response.json()[
               "detail"] == "An error occurred while processing the request.", (
        "Unexpected error message for database commit error."
    )


@pytest.mark.asyncio
async def test_refresh_access_token_success(client, db_session, jwt_manager,
                                            seed_user_groups):
    """
    Test successful access token refresh.

    Validates that a new access token is returned when a valid refresh token is provided.
    Steps:
    - Create an active user in the database.
    - Log in the user to obtain a refresh token.
    - Use the refresh token to obtain a new access token.
    - Verify that the new access token contains the correct user ID.
    """
    user_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }
    stmt = select(UserGroupModel).where(
        UserGroupModel.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"]
    }
    login_response = await client.post("/api/v1/accounts/login/",
                                       json=login_payload)
    assert login_response.status_code == 201, "Expected status code 201 for successful login."
    login_data = login_response.json()
    refresh_token = login_data["refresh_token"]

    refresh_payload = {"refresh_token": refresh_token}
    refresh_response = await client.post(
        "/api/v1/accounts/refresh/", json=refresh_payload
    )
    assert refresh_response.status_code == 200, "Expected status code 200 for successful token refresh."
    refresh_data = refresh_response.json()
    assert "access_token" in refresh_data, "Access token is missing in the response."
    assert refresh_data["access_token"], "Access token is empty."

    access_token_data = jwt_manager.decode_access_token(
        refresh_data["access_token"])
    assert access_token_data[
               "user_id"] == user.id, "Access token does not contain correct user ID."


@pytest.mark.asyncio
async def test_refresh_access_token_expired_token(client, jwt_manager):
    """
    Test refresh token with expired token.

    Validates that a 400 status code and "Token has expired." message are returned
    when the refresh token is expired.
    """
    expired_token = jwt_manager.create_refresh_token(
        {"user_id": 1},
        expires_delta=timedelta(days=-1)
    )

    refresh_payload = {"refresh_token": expired_token}
    refresh_response = await client.post("/api/v1/accounts/refresh/",
                                         json=refresh_payload)

    assert refresh_response.status_code == 400, "Expected status code 400 for expired token."
    assert refresh_response.json()[
               "detail"] == "Token has expired.", "Unexpected error message."


@pytest.mark.asyncio
async def test_refresh_access_token_token_not_found(client, jwt_manager):
    """
    Test refresh token when token is not found in the database.

    Validates that a 401 status code and 'Refresh token not found.' message
    are returned when the refresh token is not stored in the database.
    """
    refresh_token = jwt_manager.create_refresh_token({"user_id": 1})
    refresh_payload = {"refresh_token": refresh_token}
    refresh_response = await client.post("/api/v1/accounts/refresh/",
                                         json=refresh_payload)

    assert refresh_response.status_code == 401, "Expected status code 401 for token not found."
    assert refresh_response.json()[
               "detail"] == "Refresh token not found.", "Unexpected error message."


@pytest.mark.asyncio
async def test_refresh_access_token_user_not_found(client, db_session,
                                                   jwt_manager,
                                                   seed_user_groups):
    """
    Test refresh token when user ID inside the token does not exist in the database.

    Validates that a 404 status code and "User not found." message
    are returned when the user ID in the token is invalid.

    Steps:
    - Create a new active user.
    - Generate a refresh token with an invalid user ID.
    - Store the refresh token in the database.
    - Attempt to refresh the access token using the invalid refresh token.
    - Verify that the endpoint returns a 404 error with the expected message.
    """
    user_payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }

    stmt = select(UserGroupModel).where(
        UserGroupModel.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id
    )
    user.is_active = True
    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id,
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    refresh_token = jwt_manager.create_refresh_token(
        {"user_id": user.id})

    refresh_token_record = RefreshTokenModel.create(
        user_id=user.id,
        days_valid=7,
        token=refresh_token
    )
    db_session.add(refresh_token_record)
    await db_session.commit()
    await db_session.delete(user)
    await db_session.commit()

    refresh_payload = {"refresh_token": refresh_token}
    refresh_response = await client.post("/api/v1/accounts/refresh/",
                                         json=refresh_payload)

    assert refresh_response.status_code == 401, "Expected status code 401 for not exist refresh token in db."
    assert refresh_response.json()[
               "detail"] == "Refresh token not found.", "Unexpected error message."


@pytest.mark.asyncio
async def test_new_activation_latter_send_success(client, db_session,
                                                  seed_user_groups):
    """
    Test old activation token is deleted, new one created, activation letter is sent

    Validates that a new user and an activation token are created in the database.
    """
    payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }

    response = await client.post("/api/v1/accounts/register/", json=payload)
    assert response.status_code == 201, "Expected status code 201 Created."
    response_data = response.json()
    assert response_data["email"] == payload[
        "email"], "Returned email does not match."
    assert "id" in response_data, "Response does not contain user ID."

    stmt_user = select(UserModel).where(UserModel.email == payload["email"])
    result = await db_session.execute(stmt_user)
    created_user = result.scalars().first()
    assert created_user is not None, "User was not created in the database."
    assert created_user.email == payload[
        "email"], "Created user's email does not match."

    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == created_user.id)
    old_activation_token = await db_session.execute(stmt_token)

    response = await client.post("/api/v1/accounts/new_activation_token/",
                                 json=payload)
    assert response.status_code == 201, "Expected status code 201 Created."
    response_data = response.json()
    assert response_data["email"] == payload[
        "email"], "Returned email does not match."
    assert "id" in response_data, "Response does not contain user ID."
    stmt_token = select(ActivationTokenModel).where(
        ActivationTokenModel.user_id == created_user.id)
    result = await db_session.execute(stmt_token)
    tokens = result.scalars().all()
    assert len(
        tokens) <= 1, "Only one activation token should be in the database."

    assert len(
        tokens) == 1, "Activation token was not created in the database."
    activation_token = tokens[0]
    assert activation_token.user_id == created_user.id, "Activation token's user_id does not match."
    assert activation_token.token is not None, "Activation token has no token value."
    assert activation_token != old_activation_token, "Old token not deleted, new one not created"
    expires_at = activation_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > datetime.now(
        timezone.utc), "Activation token is already expired."


@pytest.mark.asyncio
async def test_new_activation_latter_user_not_found(
        client, db_session, seed_user_groups
):
    """
    Test endpoint if user with received email is not exists in database
    """
    payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }

    response = await client.post("/api/v1/accounts/new_activation_token/",
                                 json=payload)
    assert response.status_code == 400, "Expected status code 400_BAD_REQUEST."
    stmt_token = select(ActivationTokenModel)
    result = await db_session.execute(stmt_token)
    token = result.scalars().all()
    assert len(token) == 0, "activation token should not be created if user with recived email not exists"


@pytest.mark.asyncio
async def test_new_activation_latter_with_not_valid_password(
        client, db_session, seed_user_groups
):
    """
    Test endpoint if password is not valid
    """
    payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }

    response = await client.post("/api/v1/accounts/register/", json=payload)
    assert response.status_code == 201, "Expected status code 201 Created."
    stmt_token = select(ActivationTokenModel)
    result = await db_session.execute(stmt_token)
    old_token = token = result.scalars().first()

    payload["password"] = "IncorrectStrongPassword123!"

    response = await client.post("/api/v1/accounts/new_activation_token/",
                                 json=payload)

    assert response.status_code == 400, "Expected status code 400_BAD_REQUEST."
    stmt_token = select(ActivationTokenModel)
    result = await db_session.execute(stmt_token)
    tokens = result.scalars().all()
    assert len(
        tokens) == 1, "new activation token should not be created if password not valid"
    token = tokens[0]
    assert old_token == token, "old token should not be deleted if password not valid"


@pytest.mark.asyncio
async def test_new_activation_latter_if_user_already_activated(
        client, db_session, seed_user_groups
):
    """
    Test endpoint if account is already activated
    """
    payload = {
        "email": "testuser@example.com",
        "password": "StrongPassword123!"
    }

    response = await client.post("/api/v1/accounts/register/", json=payload)
    assert response.status_code == 201, "Expected status code 201 Created."
    stmt = select(UserModel).options(joinedload(UserModel.activation_token))
    result = await db_session.execute(stmt)
    user = result.scalars().first()
    user.is_active = True
    await db_session.commit()

    response = await client.post("/api/v1/accounts/new_activation_token/",
                                 json=payload)

    assert response.status_code == 409, "Expected status code 409_CONFLICT."
    await db_session.refresh(user)
    assert user.activation_token is None, "If user is already active, activation_token should be deleted"


async def is_refresh_token_deleted(db_session, user_id: int) -> bool:
    """
    If refresh token no exists return True, else False
    """
    stmt = select(RefreshTokenModel).where(
        RefreshTokenModel.user_id == user_id)
    result = await db_session.execute(stmt)
    db_refresh_token = result.scalars().first()
    return not bool(db_refresh_token)


@pytest.mark.asyncio
async def test_logout_success(client, db_session, create_activate_login_user):
    """
    Test logout endpoint with valid token.
    """
    logged_user_data = await create_activate_login_user()
    access_token = logged_user_data["access_token"]

    # Logout
    response = await client.post(
        "/api/v1/accounts/logout/",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200, "Expected status code 200."

    # Check refresh_token is deleted
    assert await is_refresh_token_deleted(db_session, logged_user_data[
        "user"].id) is True, "refresh_token should be deleted"


@pytest.mark.asyncio
async def test_logout_no_header(client, db_session, activate_and_login_user):
    """
    Test logout endpoint with no header.
    """
    # Logout
    response = await client.post(
        "/api/v1/accounts/logout/",
        headers={}
    )
    assert response.status_code == 422, "Expected status code 422."

    # Check refresh_token is deleted
    assert await is_refresh_token_deleted(db_session, activate_and_login_user[
        "user"].id) is False, "refresh_token should not be deleted"


@pytest.mark.asyncio
async def test_logout_no_header(client, db_session, create_activate_login_user):
    """
    Test logout endpoint with incorrect structure header
    """
    logged_user_data = await create_activate_login_user()
    access_token = logged_user_data["access_token"]
    # Logout
    response = await client.post(
        "/api/v1/accounts/logout/",
        headers={"Authorization": f"{access_token}"}
    )
    assert response.status_code == 401, "Expected status code 401_UNAUTHORIZED."

    # Check refresh_token is not deleted
    assert await is_refresh_token_deleted(db_session, logged_user_data[
        "user"].id) is False, "refresh_token should not be deleted"

    response = await client.post(
        "/api/v1/accounts/logout/",
        headers={"Authorization": f"Bearer{access_token}"}
    )
    assert response.status_code == 401, "Expected status code 401_UNAUTHORIZED."

    # Check refresh_token is not deleted
    assert await is_refresh_token_deleted(db_session, logged_user_data[
        "user"].id) is False, "refresh_token should not be deleted"

    response = await client.post(
        "/api/v1/accounts/logout/",
        headers={"Authorization": f"Token {access_token}"}
    )
    assert response.status_code == 401, "Expected status code 401_UNAUTHORIZED."

    # Check refresh_token is deleted
    assert await is_refresh_token_deleted(db_session, logged_user_data[
        "user"].id) is False, "refresh_token should not be deleted"


@pytest.mark.asyncio
async def test_logout_invalid_token(
        client, db_session, create_activate_login_user, jwt_manager
):
    """
    Test logout endpoint with incorrect token
    """
    invalid_token = "invalid_token"
    # Logout
    response = await client.post(
        "/api/v1/accounts/logout/",
        headers={"Authorization": f"Bearer {invalid_token}"}
    )
    assert response.status_code == 401, "Expected status code 401_UNAUTHORIZED."

    logged_user_data = await create_activate_login_user()

    # Check refresh_token is deleted
    assert await is_refresh_token_deleted(db_session, logged_user_data[
        "user"].id) is False, "refresh_token should not be deleted"

    valid_expired_token = jwt_manager.create_access_token(
        data={"user_id": logged_user_data["user"].id},
        expires_delta=timedelta(seconds=-1))

    response = await client.post(
        "/api/v1/accounts/logout/",
        headers={"Authorization": f"Bearer {valid_expired_token}"}
    )
    assert response.status_code == 401, "Expected status code 401_UNAUTHORIZED."

    # Check refresh_token is deleted
    assert await is_refresh_token_deleted(db_session, logged_user_data[
        "user"].id) is False, "refresh_token should not be deleted"

@pytest.mark.asyncio
async def test_reset_password_with_valid_credentials(
        client, db_session, create_activate_login_user
):
    user_data = await create_activate_login_user()
    user = user_data["user"]
    new_password = "NewStrongPassword123!"

    request_data = {
        "email": user_data["payload"]["email"],
        "current_password": user_data["payload"]["password"],
        "password": new_password

    }
    response = await client.post(
        "/api/v1/accounts/change-password/",
        json=request_data
    )
    assert response.status_code == 200, "Expected status code 200 for successful reset password."
    await db_session.refresh(user)
    assert user.verify_password(new_password) is True, "new password should be hashed and created in db"


@pytest.mark.asyncio
async def test_reset_password_with_invalid_old_password(
        client, db_session, create_activate_login_user
):
    user_data = await create_activate_login_user()
    user = user_data["user"]
    old_password = user_data["payload"]["password"]
    new_password = "NewStrongPassword123!"

    request_data = {
        "email": user_data["payload"]["email"],
        "current_password": "incorrectStrongPassword123!",
        "password": new_password

    }
    response = await client.post(
        "/api/v1/accounts/change-password/",
        json=request_data
    )
    assert response.status_code == 400, "Expected status code 400 if provided incorect current password."
    await db_session.refresh(user)
    assert user.verify_password(old_password) is True, "Password in DB must remain unchanged after invalid attempt"


@pytest.mark.asyncio
async def test_reset_password_without_old_password(
        client, db_session, create_activate_login_user
):
    user_data = await create_activate_login_user()
    user = user_data["user"]
    old_password = user_data["payload"]["password"]
    new_password = "NewStrongPassword123!"

    request_data = {
        "email": user_data["payload"]["email"],
        "password": new_password
    }
    response = await client.post(
        "/api/v1/accounts/change-password/",
        json=request_data
    )
    assert response.status_code == 422, "Expected 422 due to missing current_password field in request payload"
    response_json = response.json()
    assert "current_password" in response_json["detail"][0]["loc"], "Error should be related to missing 'current_password'"
    await db_session.refresh(user)
    assert user.verify_password(old_password) is True, "Password in DB must remain unchanged after invalid attempt"


@pytest.mark.asyncio
async def test_reset_password_with_not_existing_email(
        client, db_session, create_activate_login_user
):
    user_data = await create_activate_login_user()
    user = user_data["user"]
    old_password = user_data["payload"]["password"]
    new_password = "NewStrongPassword123!"
    request_data = {
        "email": "not_existing@example.com",
        "current_password": user_data["payload"]["password"],
        "password": new_password

    }
    response = await client.post(
        "/api/v1/accounts/change-password/",
        json=request_data
    )
    assert response.status_code == 400, "Expected status code 400 if provided not existing email."
    await db_session.refresh(user)
    assert user.verify_password(old_password) is True, "Password in DB must remain unchanged after invalid attempt"


@pytest.mark.asyncio
async def test_success_change_user_group(
        client, db_session, create_activate_login_user
):
    """
    Test that admin can change user`s user_group
    steps:
    1. Create, activate, login user.
    2. Create,  activate, login admin.
    3. Request change_user_group endpoint with admin access token
    4. Check that we get the correct status code
    5. Check that user`s group_id was changed in db with correct value
    """
    user_data = await create_activate_login_user(group_name="user")
    user = user_data["user"]
    admin_data = await create_activate_login_user(group_name="admin")
    headers = {
        "Authorization": f"Bearer {admin_data['access_token']}"
    }
    new_group_name = "moderator"
    request_data = {
        "group_name": new_group_name
    }
    stmt = select(UserGroupModel.id).where(UserGroupModel.name == request_data["group_name"])
    result = await db_session.execute(stmt)
    new_group_id = result.scalars().first()
    response = await client.patch(
        f"/api/v1/accounts/users/{user.id}/group/",
        json=request_data,
        headers=headers
    )
    assert response.status_code == 200, "Expected status code 200 group successfuly changed"
    await db_session.refresh(user)
    assert user.group_id == new_group_id, "New group id should be set"


@pytest.mark.asyncio
async def test_try_change_user_group_by_not_admin(
        client, db_session, create_activate_login_user
):
    """
    Test that not admin users can`t change user`s user_group
    steps:
    1. Create, activate, login target_user.
    2. Create,  activate, login user-"moderator".
    3. Create,  activate, login another_user-"user".
    4. Request change_user_group endpoint with moderator access token
    5. Check that we get the correct status code
    6. Check that user`s group_id was not changed in db
    7. Repeat points 4, 5, 6 with another_user and own target_user access tokens
    """
    target_user_data = await create_activate_login_user(group_name="user", prefix="target")
    target_user = target_user_data["user"]
    current_target_user_group_id = target_user.group_id


    moderator_data = await create_activate_login_user(group_name="moderator")
    moderator_headers = {
        "Authorization": f"Bearer {moderator_data['access_token']}"
    }
    request_data = {
        "group_name": "moderator"
    }

    response = await client.patch(
        f"/api/v1/accounts/users/{target_user.id}/group/",
        json=request_data,
        headers=moderator_headers
    )
    assert response.status_code == 403, "Expected status code 403, only admin can change user group"
    await db_session.refresh(target_user)
    assert target_user.group_id == current_target_user_group_id, "User group ID should not be changed"

    another_user_data = await create_activate_login_user(group_name="user")
    another_user_headers = {
        "Authorization": f"Bearer {another_user_data['access_token']}"
    }

    response = await client.patch(
        f"/api/v1/accounts/users/{target_user.id}/group/",
        json=request_data,
        headers=another_user_headers
    )
    assert response.status_code == 403, "Expected status code 403, only admin can change user group"
    await db_session.refresh(target_user)
    assert target_user.group_id == current_target_user_group_id, "User group ID should not be changed"

    target_user_headers = {
        "Authorization": f"Bearer {target_user_data['access_token']}"
    }

    response = await client.patch(
        f"/api/v1/accounts/users/{target_user.id}/group/",
        json=request_data,
        headers=target_user_headers
    )
    assert response.status_code == 403, "Expected status code 403, only admin can change user group"
    await db_session.refresh(target_user)
    assert target_user.group_id == current_target_user_group_id, "User group ID should not be changed"
