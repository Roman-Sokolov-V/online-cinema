import os
import binascii
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    HOSTING: str = "http://127.0.0.1:8000"
    BASE_DIR: Path = Path(__file__).parent.parent
    PATH_TO_DB: str = str(BASE_DIR / "database" / "source" / "theater.db")
    PATH_TO_MOVIES_CSV: str = str(BASE_DIR / "database" / "seed_data" / "imdb_top_1000.csv")

    PATH_TO_EMAIL_TEMPLATES_DIR: str = str(BASE_DIR / "notifications" / "templates")
    ACTIVATION_EMAIL_TEMPLATE_NAME: str = "activation_request.html"
    ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME: str = "activation_complete.html"
    PASSWORD_RESET_TEMPLATE_NAME: str = "password_reset_request.html"
    PASSWORD_RESET_COMPLETE_TEMPLATE_NAME: str = "password_reset_complete.html"
    ACTIVITY_NOTIFICATION: str = "activity_notification.html"

    LOGIN_TIME_DAYS: int = 7

    EMAIL_HOST: str = "host"
    EMAIL_PORT: int = 25
    EMAIL_HOST_USER: str = "testuser"
    EMAIL_HOST_PASSWORD: str = "test_password"
    EMAIL_USE_TLS: bool = False # os.getenv("EMAIL_USE_TLS", "False").lower() == "true"
    MAILHOG_API_PORT: int = 8025

    S3_STORAGE_HOST: str = "minio-theater"
    S3_STORAGE_PORT: int = 9000
    S3_STORAGE_ACCESS_KEY: str = "minioadmin"
    S3_STORAGE_SECRET_KEY: str = "some_password"
    S3_BUCKET_NAME: str = "theater-storage"
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/0"

    SUPER_USER_EMAIL: str = "admin@example.com"
    SUPER_USER_PASSWORD: str = "Admin@11"

    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    PAYMENT_SUCCESS_URL: str = "http://127.0.0.1:8000/api/v1/notifications/success/"
    PAYMENT_CANCEL_URL: str = "http://127.0.0.1:8000/api/v1/notifications/cancel/"
    STRIPE_WEBHOOK_SECRET: str

    @property
    def S3_STORAGE_ENDPOINT(self) -> str:
        return f"http://{self.S3_STORAGE_HOST}:{self.S3_STORAGE_PORT}"


class Settings(BaseAppSettings):
    POSTGRES_USER: str = "test_user"
    POSTGRES_PASSWORD: str = "test_user"
    POSTGRES_HOST: str = "test_host"
    POSTGRES_DB_PORT: int = 5432
    POSTGRES_DB: str = "test_db"

    SECRET_KEY_ACCESS: str = str(binascii.hexlify(os.urandom(32)))
    SECRET_KEY_REFRESH: str = str(binascii.hexlify(os.urandom(32)))
    JWT_SIGNING_ALGORITHM: str = "HS256"


class TestingSettings(BaseAppSettings):
    SECRET_KEY_ACCESS: str = "SECRET_KEY_ACCESS"
    SECRET_KEY_REFRESH: str = "SECRET_KEY_REFRESH"
    JWT_SIGNING_ALGORITHM: str = "HS256"

    def model_post_init(self, __context: dict[str, Any] | None = None) -> None:
        object.__setattr__(self, 'PATH_TO_DB', ":memory:")
        object.__setattr__(
            self,
            'PATH_TO_MOVIES_CSV',
            str(self.BASE_DIR / "database" / "seed_data" / "imdb_top_1000.csv")
        )
