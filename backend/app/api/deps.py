from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.email import EmailSender, get_email_sender
from app.errors import Forbidden, NotAuthenticated
from app.models import Customer, Staff
from app.ratelimit import Counter, get_counter
from app.security import TokenKind, decode_access_token
from app.storage import Storage, get_storage

_bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]
FileStorage = Annotated[Storage, Depends(get_storage)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
Mailer = Annotated[EmailSender, Depends(get_email_sender)]
RateCounter = Annotated[Counter, Depends(get_counter)]


def get_client_ip(request: Request) -> str:
    """The caller's IP address. Behind the proxy, uvicorn takes it from X-Forwarded-For
    (--proxy-headers); the web apps' servers pass on their visitor's address the same way."""
    return request.client.host if request.client else "unknown"


ClientIP = Annotated[str, Depends(get_client_ip)]

# What a staff member who still has to set up two-step login may use.
TWO_FACTOR_SETUP_PATHS = {"/staff/me", "/staff/me/two-factor/setup", "/staff/me/two-factor/enable"}
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


class TwoFactorSetupRequired(Forbidden):
    code = "two_factor_setup_required"


def get_current_staff(db: DB, credentials: Credentials, request: Request) -> Staff:
    staff = db.get(Staff, _subject_id(credentials, "staff"))
    if staff is None or not staff.is_active:
        raise NotAuthenticated("Your session is invalid or has expired. Log in again.")
    if (
        get_settings().require_staff_two_factor
        and staff.totp_enabled_at is None
        and request.url.path not in TWO_FACTOR_SETUP_PATHS
    ):
        raise TwoFactorSetupRequired("Set up two-step login before using the console.")
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
