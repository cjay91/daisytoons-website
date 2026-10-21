from fastapi import APIRouter, status

from app.api.deps import DB, CurrentCustomer
from app.schemas import CustomerOut, CustomerRegister, LoginRequest, Token
from app.security import create_access_token
from app.services import accounts

router = APIRouter(tags=["customer auth"])


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(db: DB, body: CustomerRegister) -> CustomerOut:
    customer = accounts.register_customer(db, **body.model_dump())
    return CustomerOut.model_validate(customer)


@router.post("/auth/login")
def login(db: DB, body: LoginRequest) -> Token:
    customer = accounts.authenticate_customer(db, email=body.email, password=body.password)
    return Token(access_token=create_access_token("customer", customer.id))


@router.get("/me")
def me(customer: CurrentCustomer) -> CustomerOut:
    return CustomerOut.model_validate(customer)
