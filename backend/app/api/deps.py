from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import NotAuthenticated
from app.models import Customer, Staff
from app.security import TokenKind, decode_access_token
from app.storage import Storage, get_storage

_bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]
FileStorage = Annotated[Storage, Depends(get_storage)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


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


CurrentCustomer = Annotated[Customer, Depends(get_current_customer)]
CurrentStaff = Annotated[Staff, Depends(get_current_staff)]
