"""Background jobs, run as their own process: python -m app.worker

Every minute: cancel unpaid orders past their reservation time (releasing their stock), retry
any confirmation or shipping emails that failed to send, and update the search index for
products and knowledge that changed.
"""

import logging
import time

import redis

from app.config import get_settings
from app.db import SessionLocal
from app.email import get_email_sender
from app.embeddings import get_embedder
from app.errors_tracking import init_error_tracking
from app.services.fulfilment import send_missing_tracking_emails
from app.services.orders import release_expired_orders, send_missing_confirmations
from app.services.search import index_knowledge, index_products

log = logging.getLogger("app.worker")

INTERVAL_SECONDS = 60
# Set after every successful run; GET /health/ready reports a stopped worker when it's old.
HEARTBEAT_KEY = "worker:heartbeat"


def heartbeat() -> None:
    try:
        client = redis.Redis.from_url(get_settings().redis_url, socket_timeout=2)
        client.set(HEARTBEAT_KEY, str(time.time()), ex=24 * 60 * 60)
    except redis.RedisError:
        log.warning("Could not record the worker heartbeat: Redis is unavailable")


def run_once() -> None:
    with SessionLocal() as db:
        released = release_expired_orders(db)
        sent = send_missing_confirmations(db, get_email_sender())
        tracking = send_missing_tracking_emails(db, get_email_sender())
    if released or sent or tracking:
        log.info(
            "Released %d expired orders, sent %d confirmation and %d shipping emails",
            released,
            sent,
            tracking,
        )
    index_search()
    heartbeat()


def index_search() -> None:
    """Separate from the order jobs, so a search problem (say, the embeddings service being
    down) never stops them."""
    try:
        with SessionLocal() as db:
            products = index_products(db, get_embedder())
            documents = index_knowledge(db, get_embedder())
    except Exception:
        log.exception("Updating the search index failed")
        return
    if products or documents:
        log.info("Indexed %d products and %d knowledge documents for search", products, documents)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_error_tracking("worker")
    log.info("Worker started; checking every %d seconds", INTERVAL_SECONDS)
    while True:
        try:
            run_once()
        except Exception:
            # Keep going: one bad run (say, the database restarting) shouldn't stop the worker.
            log.exception("Worker run failed")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
