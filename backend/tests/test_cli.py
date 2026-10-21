from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.models import Staff, StaffRole


def test_create_admin(db: Session, monkeypatch):
    monkeypatch.setattr(cli, "SessionLocal", lambda: db)
    monkeypatch.setenv("ADMIN_PASSWORD", "first-admin-password")

    exit_code = cli.main(["create-admin", "--email", "Owner@Example.com", "--name", "Owner"])

    assert exit_code == 0
    admin = db.scalar(select(Staff).where(Staff.email == "owner@example.com"))
    assert admin.role == StaffRole.ADMIN


def test_create_admin_rejects_short_password(db: Session, monkeypatch):
    monkeypatch.setattr(cli, "SessionLocal", lambda: db)
    monkeypatch.setenv("ADMIN_PASSWORD", "short")

    assert cli.main(["create-admin", "--email", "a@example.com", "--name", "A"]) == 1
