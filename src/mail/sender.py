"""Minimal SMTP sender for the daily stock report.

Configuration comes from the same ALLBUYBOTCONF secret every other
credential in this repo comes from; there is deliberately no local
fallback path, because an untested fallback is worse than a single
well-understood one.
"""

import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class MailConfigurationError(RuntimeError):
    """Raised when sending was requested but the config is incomplete."""


@dataclass(frozen=True)
class MailSender:
    host: str
    port: int
    user: str
    password: str
    sender: str

    @classmethod
    def from_env(cls) -> "MailSender":
        missing = [
            name
            for name in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD")
            if not os.getenv(name)
        ]
        if missing:
            raise MailConfigurationError(
                f"Missing SMTP settings {missing}; add them to ALLBUYBOTCONF"
            )

        user = os.getenv("SMTP_USER")
        return cls(
            host=os.getenv("SMTP_HOST"),
            port=int(os.getenv("SMTP_PORT", "587")),
            user=user,
            password=os.getenv("SMTP_PASSWORD"),
            sender=os.getenv("SMTP_FROM", user),
        )

    def build(self, to: str, subject: str, body: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        return message

    def send(self, message: EmailMessage) -> None:
        logger.info("Sending %r to %s", message["Subject"], message["To"])
        with smtplib.SMTP(self.host, self.port) as smtp:
            smtp.starttls()
            smtp.login(self.user, self.password)
            smtp.send_message(message)
