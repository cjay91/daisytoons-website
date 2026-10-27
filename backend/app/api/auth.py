from fastapi import APIRouter, Response, status

from app.api.deps import DB, ClientIP, CurrentCustomer, RateCounter
from app.ratelimit import LOGIN_PER_ACCOUNT, LOGIN_PER_IP, REGISTER_PER_IP, check
from app.schemas import (
    AddressIn,
    AddressOut,
    CustomerOut,
    CustomerRegister,
    LoginRequest,
    OrderOut,
    OrderSummaryOut,
    Token,
)
from app.security import create_access_token
from app.services import accounts, customers

router = APIRouter(tags=["customer auth"])


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(db: DB, counter: RateCounter, ip: ClientIP, body: CustomerRegister) -> CustomerOut:
    check(counter, REGISTER_PER_IP, ip)
    customer = accounts.register_customer(db, **body.model_dump())
    return CustomerOut.model_validate(customer)


@router.post("/auth/login")
def login(db: DB, counter: RateCounter, ip: ClientIP, body: LoginRequest) -> Token:
    check(counter, LOGIN_PER_IP, "customer", ip)
    check(counter, LOGIN_PER_ACCOUNT, "customer", ip, body.email)
    customer = accounts.authenticate_customer(db, email=body.email, password=body.password)
    return Token(access_token=create_access_token("customer", customer.id))


@router.get("/me")
def me(customer: CurrentCustomer) -> CustomerOut:
    return CustomerOut.model_validate(customer)


@router.get("/me/orders")
def my_orders(db: DB, customer: CurrentCustomer) -> list[OrderSummaryOut]:
    return customers.list_orders(db, customer)


@router.get("/me/orders/{order_number}")
def my_order(db: DB, customer: CurrentCustomer, order_number: str) -> OrderOut:
    return OrderOut.model_validate(customers.get_order(db, customer, order_number))


@router.get("/me/addresses")
def my_addresses(db: DB, customer: CurrentCustomer) -> list[AddressOut]:
    return [AddressOut.model_validate(a) for a in customers.list_addresses(db, customer)]


@router.post("/me/addresses", status_code=status.HTTP_201_CREATED)
def add_address(db: DB, customer: CurrentCustomer, body: AddressIn) -> AddressOut:
    return AddressOut.model_validate(customers.create_address(db, customer, body))


@router.put("/me/addresses/{address_id}")
def change_address(
    db: DB, customer: CurrentCustomer, address_id: int, body: AddressIn
) -> AddressOut:
    return AddressOut.model_validate(customers.update_address(db, customer, address_id, body))


@router.delete("/me/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_address(db: DB, customer: CurrentCustomer, address_id: int) -> Response:
    customers.delete_address(db, customer, address_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
