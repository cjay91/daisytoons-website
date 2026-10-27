"""Two-step login for staff, with codes from an authenticator app (TOTP, RFC 6238).

Setup: start_setup gives a secret to add to the app, and enable turns two-step login on once the
person types a code from it. After that, a staff login needs the password and then a code.
"""

import time
from datetime import UTC, datetime

import pyotp
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import Conflict, InvalidCredentials, NotFound
from app.models import Staff
from app.permissions import Permission, require

ISSUER = "Daisytoons console"
# Accept the code before and after the current one, for a phone clock that is slightly off.
DRIFT_STEPS = 1


def is_enabled(staff: Staff) -> bool:
    return staff.totp_enabled_at is not None and staff.totp_secret is not None


def _lock(db: Session, staff_id: int) -> Staff:
    return db.scalar(
        select(Staff)
        .where(Staff.id == staff_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def check_code(db: Session, staff: Staff, code: str) -> bool:
    """Whether the code is right. Each code works once. Records it; does not commit."""
    staff = _lock(db, staff.id)
    if staff.totp_secret is None:
        return False
    code = code.replace(" ", "")
    totp = pyotp.TOTP(staff.totp_secret)
    now = int(time.time())
    for offset in range(-DRIFT_STEPS, DRIFT_STEPS + 1):
        at = now + offset * totp.interval
        step = at // totp.interval
        if totp.verify(code, for_time=at, valid_window=0):
            if staff.totp_last_step is not None and step <= staff.totp_last_step:
                return False
            staff.totp_last_step = step
            return True
    return False


def start_setup(db: Session, staff: Staff) -> tuple[str, str]:
    """A new secret for the authenticator app. Returns (secret, otpauth:// link for a QR code)."""
    if is_enabled(staff):
        raise Conflict("Two-step login is already on. Ask an admin to reset it first.")
    staff.totp_secret = pyotp.random_base32()
    staff.totp_last_step = None
    db.commit()
    url = pyotp.TOTP(staff.totp_secret).provisioning_uri(name=staff.email, issuer_name=ISSUER)
    return staff.totp_secret, url


def enable(db: Session, staff: Staff, code: str) -> Staff:
    if is_enabled(staff):
        raise Conflict("Two-step login is already on.")
    if staff.totp_secret is None:
        raise Conflict("Start the setup first.")
    if not check_code(db, staff, code):
        db.rollback()
        raise InvalidCredentials(
            "That code isn't right. Check the time on your phone and try again."
        )
    staff.totp_enabled_at = datetime.now(UTC)
    db.commit()
    return staff


def verify_login(db: Session, staff: Staff, code: str) -> None:
    if not is_enabled(staff) or not check_code(db, staff, code):
        db.commit()
        raise InvalidCredentials("That code isn't right. Try the newest code in your app.")
    db.commit()


def reset(db: Session, actor: Staff, staff_id: int) -> Staff:
    """Turn two-step login off for someone who lost their phone, so they can set it up again."""
    require(actor, Permission.MANAGE_STAFF, "Only admins can reset two-step login.")
    staff = db.get(Staff, staff_id)
    if staff is None:
        raise NotFound("Staff member not found.")
    clear(staff)
    db.commit()
    return staff


def clear(staff: Staff) -> None:
    staff.totp_secret = None
    staff.totp_enabled_at = None
    staff.totp_last_step = None
