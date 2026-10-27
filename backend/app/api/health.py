import time

import redis
from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DB
from app.config import get_settings
from app.worker import HEARTBEAT_KEY

router = APIRouter(tags=["health"])

# The worker runs every minute; a heartbeat older than this means it has stopped.
WORKER_STALE_SECONDS = 5 * 60


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: str
    worker: str


@router.get("/health")
def health() -> HealthResponse:
    """The API process is up. Used by Docker to know when the container is ready."""
    return HealthResponse(status="ok")


@router.get("/health/ready")
def ready(db: DB, response: Response) -> ReadyResponse:
    """For the uptime monitor: the database answers and the background worker is running.
    Anything wrong gives a 503, which the monitor turns into an alert."""
    try:
        db.execute(text("select 1"))
        database = "ok"
    except Exception:
        database = "unreachable"
    try:
        client = redis.Redis.from_url(get_settings().redis_url, socket_timeout=2)
        beat = client.get(HEARTBEAT_KEY)
        if beat is None:
            worker = "not running"
        elif time.time() - float(beat) > WORKER_STALE_SECONDS:
            worker = "stopped"
        else:
            worker = "ok"
    except redis.RedisError:
        worker = "unknown (redis unreachable)"
    healthy = database == "ok" and worker == "ok"
    if not healthy:
        response.status_code = 503
    return ReadyResponse(status="ok" if healthy else "failing", database=database, worker=worker)
