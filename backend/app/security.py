from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

# staff_2fa: a short-lived token between the password step and the code step of a staff login.
TokenKind = Literal["customer", "staff", "staff_2fa"]

_password_hash = PasswordHash.recommended()  # Argon2
_ALGORITHM = "HS256"

# Verified against when the email is unknown, so a login takes the same time either way.
_DUMMY_HASH = _password_hash.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, password_hash)


def create_access_token(kind: TokenKind, subject_id: int, minutes: int | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject_id),
        "kind": kind,
        "iat": now,
        "exp": now + timedelta(minutes=minutes or settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str, kind: TokenKind) -> int | None:
    """Return the subject id if the token is valid and of the expected kind, else None."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[_ALGORITHM],
            options={"require": ["sub", "kind", "exp"]},
        )
    except jwt.PyJWTError:
        return None
    if payload["kind"] != kind:
        return None
    try:
        return int(payload["sub"])
    except ValueError:
        return None
