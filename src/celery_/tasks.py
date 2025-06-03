import os
from datetime import datetime, timezone
from celery import Celery
from sqlalchemy import delete

from database import (
    get_sync_db_contextmanager,
    ActivationTokenModel
)


app = Celery("app")
app.autodiscover_tasks()
app.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
app.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
app.conf.timezone = "UTC"


@app.task()
def remove_expired_activation_tokens():
    print("remove_expired_activation_tokens starts")
    with get_sync_db_contextmanager() as db:
        stmt = delete(ActivationTokenModel).where(
            ActivationTokenModel.expires_at < datetime.now(timezone.utc))
        db.execute(stmt)
        db.commit()
        print("expired activation tokens have removed successfully")
