from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "job_intel",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.task_serializer = "json"

# Import task modules after celery_app is created so decorators register tasks
# for workers launched with `celery -A app.tasks:celery_app`.
from app.tasks import research, resume  # noqa: E402,F401
