"""Limits on how often one person can try something, such as logging in. Counts live in Redis,
so every API process shares them; tests use an in-memory counter instead.

Each limit is a fixed window: at most `limit` tries per `window` seconds for one key (such as an
IP address plus an email address). Going over gives a 429 with a Retry-After header.
"""

import logging
import math
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import redis

from app.config import get_settings
from app.errors import AppError

log = logging.getLogger(__name__)


class TooManyRequests(AppError):
    status_code = 429
    code = "too_many_requests"

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class Limit:
    name: str
    limit: int
    window: int  # seconds


# Per IP and email: someone guessing one account's password.
LOGIN_PER_ACCOUNT = Limit("login-account", 10, 15 * 60)
# Per IP: someone trying many accounts.
LOGIN_PER_IP = Limit("login-ip", 50, 15 * 60)
REGISTER_PER_IP = Limit("register-ip", 10, 60 * 60)
CHECKOUT_PER_IP = Limit("checkout-ip", 30, 60 * 60)
TWO_FACTOR_PER_ACCOUNT = Limit("two-factor", 10, 15 * 60)
# Storefront agents: each message costs money, so far fewer than a person would ever need.
CHAT_PER_IP = Limit("chat-ip", 40, 60 * 60)
GIFT_MESSAGE_PER_IP = Limit("gift-message-ip", 20, 60 * 60)


class Counter(Protocol):
    def hit(self, key: str, window: int) -> tuple[int, int]:
        """Count one try. Returns (tries in this window, seconds until the window ends)."""
        ...


class RedisCounter:
    def __init__(self, url: str) -> None:
        self.redis = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)

    def hit(self, key: str, window: int) -> tuple[int, int]:
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window, nx=True)
        pipe.ttl(key)
        count, _, ttl = pipe.execute()
        return int(count), max(int(ttl), 1)


class MemoryCounter:
    """For tests and local runs without Redis."""

    def __init__(self) -> None:
        self.windows: dict[str, tuple[int, float]] = {}

    def hit(self, key: str, window: int) -> tuple[int, int]:
        now = time.monotonic()
        count, ends = self.windows.get(key, (0, now + window))
        if now >= ends:
            count, ends = 0, now + window
        self.windows[key] = (count + 1, ends)
        return count + 1, max(math.ceil(ends - now), 1)


@lru_cache
def get_counter() -> Counter:
    return RedisCounter(get_settings().redis_url)


def check(counter: Counter, limit: Limit, *parts: str) -> None:
    key = "rl:" + ":".join([limit.name, *(part.lower() for part in parts)])
    try:
        count, retry_after = counter.hit(key, limit.window)
    except redis.RedisError:
        # Better to let a login through than to stop the shop when Redis is down.
        log.warning("Rate limit %s not checked: Redis is unavailable", limit.name)
        return
    if count > limit.limit:
        minutes = math.ceil(retry_after / 60)
        raise TooManyRequests(
            f"Too many tries. Please wait {minutes} minute{'s' if minutes != 1 else ''} "
            "and try again.",
            retry_after,
        )
