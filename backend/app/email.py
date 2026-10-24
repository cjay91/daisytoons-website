"""Outgoing email, behind a small interface so tests can capture messages instead of sending."""

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

from app.config import Settings, get_settings


@dataclass
class Email:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, email: Email) -> None: ...


class SmtpSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, email: Email) -> None:
        message = EmailMessage()
        message["From"] = self.settings.email_from
        message["To"] = email.to
        message["Subject"] = email.subject
        message.set_content(email.body)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
            if self.settings.smtp_starttls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password or "")
            smtp.send_message(message)


class MemorySender:
    """Keeps sent emails in a list. Used by tests."""

    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


@lru_cache
def get_email_sender() -> EmailSender:
    return SmtpSender(get_settings())
