import time

import pyotp
import pytest

from app.api import health
from app.config import get_settings
from app.models import StaffRole
from tests.conftest import auth_headers

PASSWORD = "staff-password"


def staff_login(client, email, password=PASSWORD):
    return client.post("/staff/auth/login", json={"email": email, "password": password})


# Rate limits


def test_repeated_wrong_passwords_are_slowed_down(client, make_customer):
    customer = make_customer()
    for _ in range(10):
        response = client.post(
            "/auth/login", json={"email": customer.email, "password": "wrong-password"}
        )
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login", json={"email": customer.email, "password": "customer-password"}
    )

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "too_many_requests"
    assert int(blocked.headers["Retry-After"]) > 0


def test_staff_logins_are_limited_too(client, make_staff):
    staff = make_staff(StaffRole.ADMIN)
    for _ in range(10):
        staff_login(client, staff.email, "wrong-password")
    assert staff_login(client, staff.email).status_code == 429


def test_one_account_being_limited_does_not_block_others(client, make_customer):
    first, second = make_customer(), make_customer()
    for _ in range(11):
        client.post("/auth/login", json={"email": first.email, "password": "nope-nope"})

    response = client.post(
        "/auth/login", json={"email": second.email, "password": "customer-password"}
    )

    assert response.status_code == 200


def test_checkout_is_limited_per_ip(client, counter):
    from app.ratelimit import CHECKOUT_PER_IP
    from tests.test_checkout import DETAILS

    counter.windows[f"rl:{CHECKOUT_PER_IP.name}:testclient"] = (
        CHECKOUT_PER_IP.limit,
        time.monotonic() + 60,
    )
    response = client.post("/checkout", json=DETAILS)
    assert response.status_code == 429


# Two-step login


def turn_on_two_factor(client, staff):
    headers = auth_headers("staff", staff.id)
    setup = client.post("/staff/me/two-factor/setup", headers=headers).json()
    totp = pyotp.TOTP(setup["secret"])
    enabled = client.post("/staff/me/two-factor/enable", json={"code": totp.now()}, headers=headers)
    assert enabled.status_code == 200, enabled.json()
    assert enabled.json()["two_factor_enabled"] is True
    return totp, setup


def test_two_factor_setup_gives_a_link_for_the_app(client, make_staff):
    staff = make_staff(StaffRole.ADMIN)
    _, setup = turn_on_two_factor(client, staff)
    assert setup["otpauth_url"].startswith("otpauth://totp/Daisytoons%20console:")


def test_login_with_two_factor_needs_the_code(client, db, make_staff):
    staff = make_staff(StaffRole.ADMIN)
    totp, _ = turn_on_two_factor(client, staff)
    staff.totp_last_step = None  # the setup code was just used; let this test reuse the clock
    db.flush()

    first = staff_login(client, staff.email).json()
    assert first["two_factor_required"] is True and first["access_token"] is None

    wrong = client.post(
        "/staff/auth/two-factor",
        json={"challenge_token": first["challenge_token"], "code": "000000"},
    )
    right = client.post(
        "/staff/auth/two-factor",
        json={"challenge_token": first["challenge_token"], "code": totp.now()},
    )
    again = client.post(
        "/staff/auth/two-factor",
        json={"challenge_token": first["challenge_token"], "code": totp.now()},
    )

    assert wrong.status_code == 401
    assert right.status_code == 200
    token = right.json()["access_token"]
    me = client.get("/staff/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["two_factor_enabled"] is True
    # The same code can't be used twice.
    assert again.status_code == 401


def test_challenge_token_is_not_a_login(client, make_staff):
    staff = make_staff(StaffRole.ADMIN)
    turn_on_two_factor(client, staff)
    challenge = staff_login(client, staff.email).json()["challenge_token"]

    response = client.get("/staff/me", headers={"Authorization": f"Bearer {challenge}"})

    assert response.status_code == 401


def test_two_factor_cannot_be_set_up_twice(client, make_staff):
    staff = make_staff(StaffRole.ADMIN)
    turn_on_two_factor(client, staff)
    response = client.post("/staff/me/two-factor/setup", headers=auth_headers("staff", staff.id))
    assert response.status_code == 409


def test_admin_can_reset_someones_two_factor(client, make_staff):
    admin = make_staff(StaffRole.ADMIN)
    packer = make_staff(StaffRole.PACKER)
    turn_on_two_factor(client, packer)

    by_packer = client.post(
        f"/staff/members/{admin.id}/reset-two-factor", headers=auth_headers("staff", packer.id)
    )
    by_admin = client.post(
        f"/staff/members/{packer.id}/reset-two-factor", headers=auth_headers("staff", admin.id)
    )

    assert by_packer.status_code == 403
    assert by_admin.json()["two_factor_enabled"] is False
    assert staff_login(client, packer.email).json()["access_token"]


@pytest.fixture
def two_factor_required(monkeypatch):
    monkeypatch.setattr(get_settings(), "require_staff_two_factor", True)


def test_when_required_staff_must_set_up_two_factor_first(client, make_staff, two_factor_required):
    staff = make_staff(StaffRole.ADMIN)
    headers = auth_headers("staff", staff.id)

    blocked = client.get("/staff/orders", headers=headers)
    me = client.get("/staff/me", headers=headers)
    turn_on_two_factor(client, staff)
    allowed = client.get("/staff/orders", headers=headers)

    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "two_factor_setup_required"
    assert me.status_code == 200
    assert allowed.status_code == 200


# Headers and health


def test_api_responses_carry_security_headers(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


class FakeRedis:
    def __init__(self, value):
        self.value = value

    def get(self, _key):
        return self.value


@pytest.mark.parametrize(
    ("beat", "status", "worker"),
    [
        (lambda: str(time.time()).encode(), 200, "ok"),
        (lambda: str(time.time() - 3600).encode(), 503, "stopped"),
        (lambda: None, 503, "not running"),
    ],
)
def test_ready_reports_the_database_and_worker(client, monkeypatch, beat, status, worker):
    monkeypatch.setattr(health.redis.Redis, "from_url", lambda *a, **k: FakeRedis(beat()))

    response = client.get("/health/ready")

    assert response.status_code == status
    assert response.json()["database"] == "ok"
    assert response.json()["worker"] == worker
