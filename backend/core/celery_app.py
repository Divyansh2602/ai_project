import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def _with_ssl_reqs(url: str) -> str:
    """Upstash uses rediss:// (TLS). Celery's Redis broker/backend require an
    explicit ssl_cert_reqs param on rediss URLs or it raises at startup."""
    if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}ssl_cert_reqs=CERT_REQUIRED"
    return url


BROKER_URL = _with_ssl_reqs(REDIS_URL)
BACKEND_URL = _with_ssl_reqs(REDIS_URL)

celery_app = Celery(
    "trustsphere",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["core.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # Windows-compatible pool
    worker_pool="threads",
    worker_concurrency=4,
)
