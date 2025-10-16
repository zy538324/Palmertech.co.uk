"""SendGrid mailer utilities for Palmertech."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

import requests


class SendGridConfigurationError(RuntimeError):
    """Raised when attempting to send mail without the required configuration."""


@dataclass(frozen=True)
class SendGridMailResult:
    """Simple status container for SendGrid operations."""

    delivered: bool
    status_code: Optional[int] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        """Return True when the SendGrid request succeeded."""

        return self.delivered


class SendGridMailer:
    """Encapsulates SendGrid send operations with shared error handling."""

    def __init__(
        self,
        *,
        api_key: Optional[str],
        default_sender: str,
        logger: Optional[logging.Logger] = None,
        request_timeout: int = 15,
    ) -> None:
        self._api_key = api_key
        self._default_sender = default_sender
        self._logger = logger or logging.getLogger(__name__)
        self._timeout = request_timeout

    @property
    def is_configured(self) -> bool:
        """Return True when a SendGrid API key is available."""

        return bool(self._api_key)

    def send_html_email(
        self,
        *,
        subject: str,
        recipients: Iterable[str],
        html_body: str,
        reply_to: Optional[str] = None,
        attachments: Optional[Sequence[Mapping[str, str]]] = None,
        sender_name: str = "Palmertech",
    ) -> SendGridMailResult:
        """Send an HTML email via SendGrid's v3 API."""

        payload = {
            "personalizations": [
                {"to": _format_recipients(recipients)},
            ],
            "from": {"email": self._default_sender, "name": sender_name},
            "subject": subject,
            "content": [
                {
                    "type": "text/html",
                    "value": html_body,
                }
            ],
        }

        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        if attachments:
            payload["attachments"] = list(attachments)

        return self._dispatch(payload, context="standard email")

    def send_dynamic_template_email(
        self,
        *,
        recipient: str,
        template_id: str,
        dynamic_data: Mapping[str, str],
        reply_to: Optional[str] = None,
        sender_name: str = "Palmertech Web Team",
    ) -> SendGridMailResult:
        """Send a transactional email using a dynamic template."""

        payload = {
            "personalizations": [
                {
                    "to": [{"email": recipient}],
                    "dynamic_template_data": dict(dynamic_data),
                }
            ],
            "from": {"email": self._default_sender, "name": sender_name},
            "template_id": template_id,
        }

        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        return self._dispatch(payload, context="dynamic template email")

    def _dispatch(self, payload: Mapping[str, object], *, context: str) -> SendGridMailResult:
        """Post the payload to SendGrid and capture failure details."""

        if not self.is_configured:
            error = "SENDGRID_API_KEY is not configured"
            self._logger.error("%s aborted: %s", context.capitalize(), error)
            raise SendGridConfigurationError(error)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return SendGridMailResult(delivered=True, status_code=response.status_code)
        except requests.RequestException as exc:  # pragma: no cover - network failure handling
            status_code: Optional[int] = getattr(exc.response, "status_code", None)
            error_text: Optional[str] = getattr(exc.response, "text", None)
            self._logger.error(
                "Error sending %s via SendGrid: %s", context, exc, extra={"status_code": status_code}
            )
            if error_text:
                self._logger.error("SendGrid response: %s", error_text)
            return SendGridMailResult(delivered=False, status_code=status_code, error=str(exc))


def _format_recipients(recipients: Iterable[str]) -> Sequence[Mapping[str, str]]:
    """Return SendGrid-ready recipient dictionaries, filtering empty values."""

    formatted = [{"email": address.strip()} for address in recipients if address and address.strip()]
    if not formatted:
        raise ValueError("At least one recipient email address is required")
    return formatted
