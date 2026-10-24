"""Shopping carts. A cart belongs to a logged-in customer, or to a guest who holds its token."""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.errors import Conflict, NotFound
from app.models import Cart, CartItem, Customer, Inventory, Product
from app.pricing import ZERO, delivery_fee, gift_wrap_fee, money
from app.schemas import CartItemOut, CartOut, CartUpdate
from app.services.inventory import available
from app.storage import public_url

MAX_PER_PRODUCT = 20


def _query():
    return select(Cart).options(
        selectinload(Cart.items).selectinload(CartItem.product).selectinload(Product.images),
        selectinload(Cart.items).selectinload(CartItem.product).selectinload(Product.inventory),
    )


def _guest_cart(db: Session, token: str | None) -> Cart | None:
    if not token:
        return None
    return db.scalar(_query().where(Cart.token == token, Cart.customer_id.is_(None)))


def _merge(db: Session, guest: Cart, cart: Cart) -> None:
    """Move a guest cart's items into the customer's cart, then delete the guest cart."""
    quantities = {item.product_id: item for item in cart.items}
    for item in guest.items:
        if item.product_id in quantities:
            existing = quantities[item.product_id]
            existing.quantity = min(existing.quantity + item.quantity, MAX_PER_PRODUCT)
        else:
            cart.items.append(CartItem(product_id=item.product_id, quantity=item.quantity))
    cart.gift_wrap = cart.gift_wrap or guest.gift_wrap
    cart.gift_message = cart.gift_message or guest.gift_message
    db.delete(guest)


def find_cart(db: Session, customer: Customer | None, token: str | None) -> Cart | None:
    """The caller's cart, if they have one. A logged-in customer who still holds a guest cart
    token gets the guest cart's items merged into their own cart."""
    guest = _guest_cart(db, token)
    if customer is None:
        return guest
    cart = db.scalar(_query().where(Cart.customer_id == customer.id))
    if guest is not None:
        if cart is None:
            guest.customer_id = customer.id
            cart = guest
        else:
            _merge(db, guest, cart)
        db.commit()
        db.refresh(cart)
    return cart


def get_or_create_cart(db: Session, customer: Customer | None, token: str | None) -> Cart:
    cart = find_cart(db, customer, token)
    if cart is None:
        cart = Cart(token=secrets.token_urlsafe(32), customer_id=customer.id if customer else None)
        db.add(cart)
        db.commit()
    return cart


def set_item(db: Session, cart: Cart, product_id: int, quantity: int) -> Cart:
    """Set how many of a product are in the cart. 0 removes it."""
    item = next((i for i in cart.items if i.product_id == product_id), None)
    if quantity == 0:
        if item is not None:
            cart.items.remove(item)
            db.commit()
        return cart
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise NotFound("Product not found.")
    inventory = db.get(Inventory, product_id)
    left = available(inventory) if inventory else 0
    # Lowering a quantity is always allowed, even when stock has since run short.
    if quantity > (item.quantity if item else 0) and quantity > left:
        if left == 0:
            raise Conflict(f"{product.name} is out of stock.")
        raise Conflict(f"Only {left} of {product.name} left in stock.")
    if item is None:
        cart.items.append(CartItem(product_id=product_id, quantity=quantity))
    else:
        item.quantity = quantity
    db.commit()
    return cart


def update_cart(db: Session, cart: Cart, data: CartUpdate) -> Cart:
    if data.gift_wrap is not None:
        cart.gift_wrap = data.gift_wrap
    if data.gift_message is not None:
        cart.gift_message = data.gift_message.strip()
    db.commit()
    return cart


def cart_out(db: Session, cart: Cart | None) -> CartOut:
    settings = get_settings()
    items: list[CartItemOut] = []
    if cart is not None:
        for item in cart.items:
            product = item.product
            image = product.images[0] if product.images else None
            left = available(product.inventory) if product.is_active and product.inventory else 0
            items.append(
                CartItemOut(
                    product_id=product.id,
                    slug=product.slug,
                    name=product.name,
                    image_url=public_url(image.storage_key) if image else None,
                    unit_price=product.price,
                    quantity=item.quantity,
                    line_total=money(product.price * item.quantity),
                    available=left,
                )
            )
    subtotal = money(sum((item.line_total for item in items), ZERO))
    gift_wrap = cart.gift_wrap if cart else False
    return CartOut(
        token=cart.token if cart else None,
        items=items,
        item_count=sum(item.quantity for item in items),
        subtotal=subtotal,
        gift_wrap=gift_wrap,
        gift_message=cart.gift_message if cart else "",
        gift_wrap_fee=gift_wrap_fee(settings, gift_wrap),
        gift_wrap_price=gift_wrap_fee(settings, True),
        delivery_fee_colombo=delivery_fee(settings, subtotal, "Colombo"),
        delivery_fee_other=delivery_fee(settings, subtotal, "Kandy"),
        free_delivery_over=money(settings.free_delivery_over),
        currency=settings.currency,
    )
