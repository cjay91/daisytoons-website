"""Background jobs, run as their own process: python -m app.worker

Every minute: cancel unpaid orders past their reservation time (releasing their stock), and
retry any confirmation emails that failed to send.
"""

import logging
import time

from app.db import SessionLocal
from app.email import get_email_sender
from app.services.orders import release_expired_orders, send_missing_confirmations

log = logging.getLogger("app.worker")

INTERVAL_SECONDS = 60


def run_once() -> None:
    with SessionLocal() as db:
        released = release_expired_orders(db)
        sent = send_missing_confirmations(db, get_email_sender())
    if released or sent:
        log.info("Released %d expired orders, sent %d confirmation emails", released, sent)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
