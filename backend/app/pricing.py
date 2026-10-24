"""Delivery and gift wrap charges, and Sri Lanka's districts (used to work out delivery)."""

from decimal import Decimal

from app.config import Settings

DISTRICTS = [
    "Ampara",
    "Anuradhapura",
    "Badulla",
    "Batticaloa",
    "Colombo",
    "Galle",
    "Gampaha",
    "Hambantota",
    "Jaffna",
    "Kalutara",
    "Kandy",
    "Kegalle",
    "Kilinochchi",
    "Kurunegala",
    "Mannar",
    "Matale",
    "Matara",
    "Monaragala",
    "Mullaitivu",
    "Nuwara Eliya",
    "Polonnaruwa",
    "Puttalam",
    "Ratnapura",
    "Trincomalee",
    "Vavuniya",
]

ZERO = Decimal("0.00")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def delivery_fee(settings: Settings, subtotal: Decimal, district: str) -> Decimal:
    if subtotal >= settings.free_delivery_over:
        return ZERO
    fee = settings.delivery_fee_colombo if district == "Colombo" else settings.delivery_fee_other
    return money(fee)


def gift_wrap_fee(settings: Settings, gift_wrap: bool) -> Decimal:
    return money(settings.gift_wrap_fee) if gift_wrap else ZERO
