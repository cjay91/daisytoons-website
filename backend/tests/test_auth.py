from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings
from app.models import StaffRole
from tests.conftest import auth_headers

NEW_CUSTOMER = {"email": "Asha@Example.com", "password": "correct-horse", "full_name": "Asha"}


def register(client, **overrides):
    return client.post("/auth/register", json={**NEW_CUSTOMER, **overrides})


def login(client, email="asha@example.com", password="correct-horse"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_register_creates_customer_with_lowercase_email(client):
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "asha@example.com"
    assert "password" not in body and "password_hash" not in body


def test_register_rejects_duplicate_email(client):
    register(client)

    response = register(client, email="ASHA@example.com")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_register_rejects_short_password(client):
    response = register(client, password="short")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "password"


def test_login_returns_token_that_opens_me(client):
    register(client)

    token = login(client, email="ASHA@example.com").json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == "asha@example.com"


def test_wrong_password_and_unknown_email_get_the_same_error(client):
    register(client)

    wrong_password = login(client, password="wrong-password")
    unknown_email = login(client, email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_a_token(client):
    response = client.get("/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_expired_token_is_rejected(client):
    customer_id = register(client).json()["id"]
    expired = jwt.encode(
        {"sub": str(customer_id), "kind": "customer", "exp": datetime.now(UTC) - timedelta(1)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )

    response = client.get("/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


def test_token_signed_with_another_secret_is_rejected(client):
    customer_id = register(client).json()["id"]
    forged = jwt.encode(
        {"sub": str(customer_id), "kind": "customer", "exp": datetime.now(UTC) + timedelta(1)},
        "a-different-secret-that-is-long-enough-to-sign",
        algorithm="HS256",
    )

    assert client.get("/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_customer_token_does_not_work_on_staff_endpoints(client):
    customer_id = register(client).json()["id"]

    response = client.get("/staff/me", headers=auth_headers("customer", customer_id))

    assert response.status_code == 401


def test_staff_token_does_not_work_on_customer_endpoints(client, make_staff):
    staff = make_staff(StaffRole.ADMIN)

    assert client.get("/me", headers=auth_headers("staff", staff.id)).status_code == 401


def test_staff_login(client, make_staff):
    make_staff(StaffRole.PACKER, "packer@example.com")

    response = client.post(
        "/staff/auth/login",
        json={"email": "packer@example.com", "password": "staff-password"},
    )
    token = response.json()["access_token"]
    me = client.get("/staff/me", headers={"Authorization": f"Bearer {token}"})

    assert me.json()["role"] == "packer"


def test_inactive_staff_cannot_log_in(client, make_staff):
    make_staff(StaffRole.ADMIN, "former@example.com", is_active=False)

    response = client.post(
        "/staff/auth/login",
        json={"email": "former@example.com", "password": "staff-password"},
    )

    assert response.status_code == 401
