from celery import Celery
from config.redis import get_redis_url

redis_connection_url = get_redis_url()

celery_app = Celery(
    "alarm_worker",
    broker=redis_connection_url,
    backend=redis_connection_url,
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
)