from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "job_intel",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.task_serializer = "json"
celery_app.autodiscover_tasks(["app.tasks"])
