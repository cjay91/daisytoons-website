from fastapi import APIRouter

from app.api.deps import DB, CartToken, OptionalCustomer
from app.schemas import CartItemSet, CartOut, CartUpdate
from app.services import carts

router = APIRouter(prefix="/cart", tags=["cart"])


@router.post("")
def create_cart(db: DB, customer: OptionalCustomer, token: CartToken = None) -> CartOut:
    return carts.cart_out(db, carts.get_or_create_cart(db, customer, token))


@router.get("")
def get_cart(db: DB, customer: OptionalCustomer, token: CartToken = None) -> CartOut:
    return carts.cart_out(db, carts.find_cart(db, customer, token))


@router.patch("")
def update_cart(
    db: DB, body: CartUpdate, customer: OptionalCustomer, token: CartToken = None
) -> CartOut:
    cart = carts.get_or_create_cart(db, customer, token)
    return carts.cart_out(db, carts.update_cart(db, cart, body))


@router.put("/items/{product_id}")
def set_item(
    db: DB, product_id: int, body: CartItemSet, customer: OptionalCustomer, token: CartToken = None
) -> CartOut:
    cart = carts.get_or_create_cart(db, customer, token)
    return carts.cart_out(db, carts.set_item(db, cart, product_id, body.quantity))
