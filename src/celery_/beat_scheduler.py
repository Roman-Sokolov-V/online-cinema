from celery_.tasks import app
from celery.schedules import crontab

app.conf.beat_schedule = {
    "add_every_day_at_01_01": {
        'task': "celery_.tasks.remove_expired_activation_tokens",
        'schedule': crontab(minute=1, hour=1),
    },
}
