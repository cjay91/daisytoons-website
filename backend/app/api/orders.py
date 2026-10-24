from fastapi import APIRouter, Query

from app.api.deps import DB, CartToken, OptionalCustomer
from app.errors import Conflict
from app.pricing import DISTRICTS
from app.schemas import CheckoutOut, CheckoutRequest, OrderOut
from app.services import carts, checkout, orders

router = APIRouter(tags=["checkout"])


@router.get("/checkout/districts")
def list_districts() -> list[str]:
    return DISTRICTS


@router.post("/checkout")
def place_order(
    db: DB, body: CheckoutRequest, customer: OptionalCustomer, token: CartToken = None
) -> CheckoutOut:
    cart = carts.find_cart(db, customer, token)
    if cart is None:
        raise Conflict("Your cart is empty.")
    return checkout.checkout(db, cart, customer, body)


@router.get("/orders/{order_number}")
def get_order(db: DB, order_number: str, key: str = Query(max_length=64)) -> OrderOut:
    """The order confirmation page. The key comes from checkout and the confirmation email."""
    return OrderOut.model_validate(orders.get_order_for_key(db, order_number, key))
