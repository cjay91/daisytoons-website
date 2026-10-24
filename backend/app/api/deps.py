from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.email import EmailSender, get_email_sender
from app.errors import NotAuthenticated
from app.models import Customer, Staff
from app.security import TokenKind, decode_access_token
from app.storage import Storage, get_storage

_bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]
FileStorage = Annotated[Storage, Depends(get_storage)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
Mailer = Annotated[EmailSender, Depends(get_email_sender)]
# Guests' cart token; the storefront keeps it and sends it with every cart request.
CartToken = Annotated[str | None, Header(alias="X-Cart-Token", max_length=64)]


def _subject_id(credentials: HTTPAuthorizationCredentials | None, kind: TokenKind) -> int:
    if credentials is None:
        raise NotAuthenticated("Log in to continue.")
    subject_id = decode_access_token(credentials.credentials, kind)
    if subject_id is None:
        raise NotAuthenticated("Your session is invalid or has expired. Log in again.")
    return subject_id


def get_current_customer(db: DB, credentials: Credentials) -> Customer:
    customer = db.get(Customer, _subject_id(credentials, "customer"))
    if customer is None or not customer.is_active:
        raise NotAuthenticated("Your session is invalid or has expired. Log in again.")
    return customer


def get_current_staff(db: DB, credentials: Credentials) -> Staff:
    staff = db.get(Staff, _subject_id(credentials, "staff"))
    if staff is None or not staff.is_active:
        raise NotAuthenticated("Your session is invalid or has expired. Log in again.")
    return staff


def get_optional_customer(db: DB, credentials: Credentials) -> Customer | None:
    """The logged-in customer, or None for a guest. A bad or expired token is still an error,
    so a customer whose login ran out isn't quietly treated as a guest."""
    if credentials is None:
        return None
    return get_current_customer(db, credentials)


CurrentCustomer = Annotated[Customer, Depends(get_current_customer)]
OptionalCustomer = Annotated[Customer | None, Depends(get_optional_customer)]
CurrentStaff = Annotated[Staff, Depends(get_current_staff)]
