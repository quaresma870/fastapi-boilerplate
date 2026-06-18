"""
Email utility — sends emails via SMTP.
Degrades gracefully when SMTP is not configured (logs instead of sending).
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body_html: str) -> bool:
    """Send an email. Returns True on success, False if SMTP not configured."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.info("SMTP not configured — email to %s would say: %s", to, subject)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.EMAILS_FROM
        msg["To"] = to
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM, to, msg.as_string())

        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False


def build_reset_email(reset_url: str) -> str:
    return f"""
    <html><body>
    <h2>Password Reset</h2>
    <p>Click the link below to reset your password. This link expires in 1 hour.</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>If you did not request this, ignore this email.</p>
    </body></html>
    """
