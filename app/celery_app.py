from celery import Celery
from app.config import settings

# Initialize Celery using Redis as both broker (queue) and backend
celery_app = Celery(
    "certificate_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,  # Performance optimization: Redis counters are used instead of Celery's result backend
    worker_prefetch_multiplier=1,  # Fair distribution of jobs across worker processes
)