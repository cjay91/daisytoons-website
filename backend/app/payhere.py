"""PayHere hosted checkout: the fields the storefront posts to PayHere's payment page, and the
signature checks on the notification PayHere sends back.

https://support.payhere.lk/api-&-mobile-sdk/checkout-api
"""

import hashlib
import hmac
from decimal import Decimal

from app.config import Settings

SANDBOX_CHECKOUT_URL = "https://sandbox.payhere.lk/pay/checkout"
LIVE_CHECKOUT_URL = "https://www.payhere.lk/pay/checkout"

SUCCESS = "2"
PENDING = "0"
CANCELLED = "-1"
FAILED = "-2"
CHARGEBACK = "-3"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest().upper()  # noqa: S324 - PayHere's scheme


def format_amount(amount: Decimal) -> str:
    return f"{amount:.2f}"


def checkout_hash(settings: Settings, order_number: str, amount: Decimal, currency: str) -> str:
    secret = _md5(settings.payhere_merchant_secret)
    return _md5(
        f"{settings.payhere_merchant_id}{order_number}{format_amount(amount)}{currency}{secret}"
    )


def notification_signature(settings: Settings, fields: dict[str, str]) -> str:
    secret = _md5(settings.payhere_merchant_secret)
    return _md5(
        fields.get("merchant_id", "")
        + fields.get("order_id", "")
        + fields.get("payhere_amount", "")
        + fields.get("payhere_currency", "")
        + fields.get("status_code", "")
        + secret
    )


def signature_valid(settings: Settings, fields: dict[str, str]) -> bool:
    expected = notification_signature(settings, fields)
    return hmac.compare_digest(expected, fields.get("md5sig", "").upper())


def checkout_url(settings: Settings) -> str:
    return SANDBOX_CHECKOUT_URL if settings.payhere_sandbox else LIVE_CHECKOUT_URL
