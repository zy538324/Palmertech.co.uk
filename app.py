"""Palmertech website WSGI application."""
from __future__ import annotations

import base64
import io
import logging
import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from itsdangerous import URLSafeSerializer
from markupsafe import escape
import requests
from requests.exceptions import RequestException
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from pricing import (
    BASE_APP_FEE,
    PER_PAGE_FEE,
    current_rate,
    format_currency,
    maintenance_cost,
    pricing_summary,
)
from services.sendgrid_mailer import SendGridConfigurationError, SendGridMailer

load_dotenv()
app = Flask(__name__)
asgi_app = WsgiToAsgi(app)


@dataclass(frozen=True)
class MailSettings:
    """Container for SendGrid-related configuration."""

    api_key: Optional[str]
    default_sender: Optional[str]
    owner_recipient: Optional[str]
    requirements_template_id: Optional[str]
    requirements_recipient: Optional[str]
    fallback_contact_email: Optional[str]

    @classmethod
    def from_env(cls) -> "MailSettings":
        """Load mail configuration from environment variables."""

        return cls(
            api_key=os.getenv("SENDGRID_API_KEY"),
            default_sender=os.getenv("MAIL_DEFAULT_SENDER"),
            owner_recipient=os.getenv("MAIL_OWNER_RECIPIENT"),
            requirements_template_id=os.getenv("PALMERTECH_REQUIREMENTS_TEMPLATE_ID"),
            requirements_recipient=os.getenv("PALMERTECH_REQUIREMENTS_RECIPIENT"),
            fallback_contact_email=os.getenv("MAIL_FALLBACK_CONTACT"),
        )


MAIL_SETTINGS = MailSettings.from_env()
mailer: Optional[SendGridMailer] = None


# CAPTCHA configuration for contact form protection


@dataclass(frozen=True)
class CaptchaSettings:
    """Container for hCaptcha configuration."""

    site_key: Optional[str]
    secret_key: Optional[str]

    @classmethod
    def from_env(cls) -> "CaptchaSettings":
        """Load hCaptcha settings from the environment."""

        return cls(
            site_key=os.getenv("HCAPTCHA_SITE_KEY"),
            secret_key=os.getenv("HCAPTCHA_SECRET_KEY"),
        )


CAPTCHA_SETTINGS = CaptchaSettings.from_env()
HCAPTCHA_VERIFY_ENDPOINT = "https://hcaptcha.com/siteverify"


# Contact form spam-mitigation settings
CONTACT_FORM_TOKEN_SESSION_KEY = "contact_form_token"
CONTACT_FORM_TIME_SESSION_KEY = "contact_form_issued_at"
CONTACT_FORM_LAST_SUBMISSION_KEY = "contact_form_last_submission"
CONTACT_FORM_TOKEN_TTL = timedelta(hours=2)
CONTACT_FORM_SUBMISSION_COOLDOWN = timedelta(seconds=45)
CONTACT_FORM_MIN_MESSAGE_LENGTH = 10


def configure_logging(flask_app: Flask) -> None:
    """Configure file-based logging with rotation and archival."""

    base_dir = Path(__file__).resolve().parent
    log_dir = base_dir / "logs"
    archive_dir = base_dir / "log_archive"
    log_dir.mkdir(exist_ok=True)
    archive_dir.mkdir(exist_ok=True)

    log_file = log_dir / "flask.log"
    handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    )
    handler.setLevel(logging.INFO)
    flask_app.logger.addHandler(handler)
    flask_app.logger.setLevel(logging.INFO)

    archive_old_logs(log_dir, archive_dir, flask_app.logger)


def archive_old_logs(log_dir: Path, archive_dir: Path, logger: logging.Logger) -> None:
    """Compress logs older than 30 days on the first day of each month."""

    today = datetime.today()
    if today.day != 1:
        return

    for log_file in log_dir.glob("flask.log.*"):
        archive_base = archive_dir / log_file.name
        shutil.make_archive(str(archive_base), "zip", log_dir, log_file.name)
        log_file.unlink(missing_ok=True)
        logger.info("Archived log file: %s", log_file.name)


def resolve_secret_key(logger: logging.Logger) -> str:
    """Return the Flask secret key, generating a temporary value if required."""

    secret_key = os.getenv("SECRET_KEY")
    if secret_key:
        return secret_key

    ephemeral_key = secrets.token_urlsafe(32)
    logger.warning(
        "SECRET_KEY is not configured; generated ephemeral key for this process. "
        "Configure a persistent SECRET_KEY for production deployments."
    )
    return ephemeral_key


def initialise_mailer(settings: MailSettings, logger: logging.Logger) -> Optional[SendGridMailer]:
    """Create the SendGrid mailer if the minimum configuration exists."""

    if not settings.default_sender:
        logger.warning("MAIL_DEFAULT_SENDER is not configured; email features disabled.")
        return None

    mailer_instance = SendGridMailer(
        api_key=settings.api_key,
        default_sender=settings.default_sender,
        logger=logger,
    )

    if not settings.api_key:
        logger.warning("SENDGRID_API_KEY is not configured; email delivery will fail until provided.")

    return mailer_instance


configure_logging(app)
app.secret_key = resolve_secret_key(app.logger)
mailer = initialise_mailer(MAIL_SETTINGS, app.logger)


@app.context_processor
def inject_pricing_context() -> dict[str, object]:
    """Expose pricing helpers and formatted constants to Jinja templates."""

    return {
        "current_rate": current_rate,
        "maintenance_cost": maintenance_cost,
        "pricing_summary": pricing_summary,
        "format_currency": format_currency,
        "PRICING_BASE_APP_FEE": format_currency(BASE_APP_FEE),
        "PRICING_PER_PAGE_FEE": format_currency(PER_PAGE_FEE),
        "PRICING_BASE_APP_FEE_VALUE": BASE_APP_FEE,
        "PRICING_PER_PAGE_FEE_VALUE": PER_PAGE_FEE,
    }


def _parse_positive_int(value: Optional[str], *, default: int = 0) -> int:
    """Return a positive integer parsed from the supplied value."""

    if value is None:
        return default

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return parsed if parsed >= 0 else default


def _parse_positive_decimal(value: Optional[str]) -> Optional[Decimal]:
    """Return a non-negative decimal parsed from the supplied value."""

    if value in (None, ""):
        return None

    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        return None

    return parsed if parsed >= 0 else None


def _quantise_currency(amount: Decimal) -> Decimal:
    """Round a Decimal amount to two decimal places."""

    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _issue_contact_form_token() -> str:
    """Generate and persist a fresh anti-spam token for the contact form."""

    token = secrets.token_urlsafe(32)
    issued_at = datetime.now(timezone.utc)
    session[CONTACT_FORM_TOKEN_SESSION_KEY] = token
    session[CONTACT_FORM_TIME_SESSION_KEY] = issued_at.timestamp()
    return token


def _validate_contact_form_submission(
    *, token: Optional[str], honeypot_value: Optional[str]
) -> tuple[bool, Optional[str]]:
    """Validate anti-spam defences for the contact form submission."""

    now_utc = datetime.now(timezone.utc)

    if honeypot_value and honeypot_value.strip():
        app.logger.warning("Contact form honeypot field populated; blocking submission.")
        return False, "Your submission could not be processed. Please contact us directly."

    session_token = session.get(CONTACT_FORM_TOKEN_SESSION_KEY)
    if not token or not session_token or not secrets.compare_digest(token, session_token):
        app.logger.info("Contact form token mismatch or missing; prompting visitor to retry.")
        return False, "Your session has expired. Please refresh the page and try again."

    issued_at_ts = session.get(CONTACT_FORM_TIME_SESSION_KEY)
    if not isinstance(issued_at_ts, (int, float)):
        app.logger.info("Contact form token missing timestamp metadata; requesting resubmission.")
        return False, "Your session has expired. Please refresh the page and try again."

    issued_at = datetime.fromtimestamp(issued_at_ts, tz=timezone.utc)
    if now_utc - issued_at > CONTACT_FORM_TOKEN_TTL:
        app.logger.info("Contact form token expired; prompting visitor to refresh page.")
        return False, "Your session has expired. Please refresh the page and try again."

    last_submission_ts = session.get(CONTACT_FORM_LAST_SUBMISSION_KEY)
    if isinstance(last_submission_ts, (int, float)):
        last_submission = datetime.fromtimestamp(last_submission_ts, tz=timezone.utc)
        if now_utc - last_submission < CONTACT_FORM_SUBMISSION_COOLDOWN:
            app.logger.info("Contact form submission throttled due to rapid repeat attempts.")
            return False, "Please wait a moment before submitting again."

    return True, None


def _verify_hcaptcha(response_token: Optional[str], remote_addr: Optional[str]) -> tuple[bool, Optional[str]]:
    """Validate the hCaptcha response token with the verification endpoint."""

    if not CAPTCHA_SETTINGS.site_key or not CAPTCHA_SETTINGS.secret_key:
        app.logger.warning(
            "hCaptcha keys are not configured; contact form submissions are unprotected.")
        return True, None

    if not response_token:
        app.logger.info("Missing hCaptcha response token; prompting visitor to retry.")
        return False, "Please complete the CAPTCHA challenge to continue."

    payload = {
        "response": response_token,
        "secret": CAPTCHA_SETTINGS.secret_key,
    }

    if remote_addr:
        payload["remoteip"] = remote_addr

    try:
        verification_response = requests.post(HCAPTCHA_VERIFY_ENDPOINT, data=payload, timeout=5)
        verification_response.raise_for_status()
        result = verification_response.json()
    except (RequestException, ValueError) as exc:
        app.logger.error("hCaptcha verification failed: %s", exc)
        return False, "We could not verify the CAPTCHA. Please try again."

    if not result.get("success"):
        app.logger.info("hCaptcha challenge unsuccessful: %s", result)
        return False, "CAPTCHA verification failed. Please try again."

    app.logger.debug("hCaptcha verification succeeded for remote %s", remote_addr)
    return True, None


def _send_html_email_safe(
    *,
    context: str,
    subject: str,
    recipients: Iterable[str],
    html_body: str,
    reply_to: Optional[str] = None,
    attachments: Optional[Sequence[Mapping[str, str]]] = None,
) -> bool:
    """Safely dispatch a standard HTML email through SendGrid."""

    if mailer is None:
        app.logger.error("Mailer unavailable; %s aborted due to missing configuration.", context)
        return False

    try:
        result = mailer.send_html_email(
            subject=subject,
            recipients=recipients,
            html_body=html_body,
            reply_to=reply_to,
            attachments=attachments,
        )
        return result.ok
    except (SendGridConfigurationError, ValueError) as exc:
        app.logger.error("Failed to send %s: %s", context, exc)
        return False


def _send_dynamic_email_safe(
    *,
    context: str,
    recipient: str,
    template_id: str,
    dynamic_data: Mapping[str, str],
    reply_to: Optional[str] = None,
) -> bool:
    """Safely dispatch a dynamic template email through SendGrid."""

    if mailer is None:
        app.logger.error("Mailer unavailable; %s aborted due to missing configuration.", context)
        return False

    if not template_id:
        app.logger.error("Failed to send %s: template_id missing.", context)
        return False

    try:
        result = mailer.send_dynamic_template_email(
            recipient=recipient,
            template_id=template_id,
            dynamic_data=dynamic_data,
            reply_to=reply_to,
        )
        return result.ok
    except (SendGridConfigurationError, ValueError) as exc:
        app.logger.error("Failed to send %s: %s", context, exc)
        return False


def generate_enquiry_pdf(data: Mapping[str, str]) -> io.BytesIO:
    """Create a PDF summary of an enquiry submission."""

    app.logger.info("Generating enquiry PDF")
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    logo_path = Path(__file__).resolve().parent / "static" / "logo.png"
    if logo_path.exists():
        pdf.drawImage(str(logo_path), 50, 700, width=120, height=100, preserveAspectRatio=True, mask="auto")
        y_position = 680
    else:
        y_position = 750

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, y_position + 40, "Palmertech Project Enquiry")
    pdf.setFont("Helvetica", 12)
    y_position -= 30

    for key, value in data.items():
        pdf.drawString(50, y_position, f"{key}: {value}")
        y_position -= 25

    try:
        page_count = int(data.get("page_count", 0))
    except (TypeError, ValueError):
        page_count = 0

    pricing_info = pricing_summary(page_count)
    y_position -= 10
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y_position, "Pricing Overview")
    y_position -= 20
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y_position, f"Development Rate: {pricing_info['current_rate']}")
    y_position -= 20
    pdf.drawString(
        50,
        y_position,
        f"Maintenance ({pricing_info['pages']} pages): {pricing_info['maintenance_cost']}",
    )
    y_position -= 20
    pdf.drawString(50, y_position, "Annual Adjustment: +5% after 1 year, +10% thereafter")

    pdf.save()
    buffer.seek(0)
    return buffer


@app.route("/enquiry/<token>", methods=["GET", "POST"])
def private_enquiry(token: str):
    serializer = URLSafeSerializer(app.secret_key)
    try:
        serializer.loads(token)
        app.logger.info("Private enquiry accessed with token %s", token)
    except Exception:  # pragma: no cover - token tampering
        flash("Invalid or expired link.")
        return redirect(url_for("home"))

    if request.method == "POST":
        form_data = {key: request.form.get(key) for key in request.form}

        if not MAIL_SETTINGS.owner_recipient:
            app.logger.error("Owner recipient email is not configured; enquiry submission cannot notify staff.")
            flash("Your enquiry was captured but notifications are temporarily unavailable.")
            return redirect(url_for("home"))

        pdf_buffer = generate_enquiry_pdf(form_data)
        encoded_pdf = base64.b64encode(pdf_buffer.read()).decode("ascii")
        pdf_attachment = [
            {
                "content": encoded_pdf,
                "type": "application/pdf",
                "filename": "enquiry.pdf",
                "disposition": "attachment",
            }
        ]

        owner_email_sent = _send_html_email_safe(
            context="project enquiry owner notification",
            subject=f"New Project Enquiry from {form_data.get('name')}",
            recipients=[MAIL_SETTINGS.owner_recipient],
            html_body="<p>Project enquiry attached.</p>",
            attachments=pdf_attachment,
            reply_to=form_data.get("email"),
        )

        customer_email_sent = False
        customer_email = form_data.get("email")
        if customer_email:
            customer_email_sent = _send_html_email_safe(
                context="project enquiry customer receipt",
                subject="Your Palmertech Project Enquiry Receipt",
                recipients=[customer_email],
                html_body=(
                    "<p>Thank you for your enquiry. Please find your submitted details attached as a PDF. "
                    "We will be in touch shortly.</p>"
                ),
                attachments=pdf_attachment,
            )

        if owner_email_sent and customer_email_sent:
            flash("Your enquiry has been submitted and emailed to both parties.")
        elif owner_email_sent:
            flash("Your enquiry was received. Confirmation will follow once email delivery is restored.")
        else:
            flash("Enquiry received, but notifications could not be delivered. We will follow up shortly.")

        return redirect(url_for("home"))

    return render_template("enquiry_form.html")


@app.route("/services/web-mobile")
def services_web_mobile():
    return render_template("services_web_mobile.html")


@app.route("/services/api")
def services_api():
    return render_template("services_api.html")


@app.route("/services/php-html-css-js")
def services_php_html_css_js():
    return render_template("services_php_html_css_js.html")


@app.route("/services/support")
def services_support():
    return render_template("services_support.html")


@app.route("/services")
def services():
    return render_template("services.html")


@app.route("/testimonials")
def testimonials():
    return render_template("testimonials.html")


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/project-requirements", methods=["GET"])
def project_requirements():
    """Render the private project requirements intake form."""

    default_page_count = 5
    return render_template(
        "project_requirements.html",
        default_page_count=default_page_count,
        pricing_info=pricing_summary(default_page_count),
    )


@app.post("/api/palmertech/requirements")
def submit_requirements():
    """Accept and forward confidential project requirement submissions."""

    required_fields = ("name", "email", "project_type", "requirements", "estimated_hours", "page_count")
    form_data = {field: (request.form.get(field) or "").strip() for field in request.form}

    missing = [field for field in required_fields if not form_data.get(field)]
    if missing:
        app.logger.warning("Project requirements submission missing fields: %s", ", ".join(missing))
        return {
            "status": "error",
            "message": "Please complete all required fields before submitting the form.",
        }, 400

    page_count = _parse_positive_int(form_data.get("page_count"), default=0)
    estimated_hours = _parse_positive_decimal(form_data.get("estimated_hours"))
    if estimated_hours is None:
        app.logger.warning("Project requirements submission missing or invalid estimated_hours value.")
        return {
            "status": "error",
            "message": "Estimated hours must be a non-negative number.",
        }, 400

    rate = current_rate()
    maintenance_total = maintenance_cost(page_count)
    development_total = _quantise_currency(rate * estimated_hours)

    safe_data = {
        "name": str(escape(form_data.get("name", ""))),
        "email": str(escape(form_data.get("email", ""))),
        "company": str(escape(form_data.get("company", ""))),
        "project_type": str(escape(form_data.get("project_type", ""))),
        "budget": str(escape(form_data.get("budget", ""))),
        "timeline": str(escape(form_data.get("timeline", ""))),
        "requirements": str(escape(form_data.get("requirements", ""))),
        "year": str(datetime.utcnow().year),
        "estimated_hours": f"{estimated_hours}",
        "page_count": str(page_count),
        "development_rate": format_currency(rate),
        "development_estimate": format_currency(development_total),
        "maintenance_estimate": format_currency(maintenance_total),
    }

    if not MAIL_SETTINGS.requirements_template_id or not MAIL_SETTINGS.requirements_recipient:
        app.logger.error("Project requirements email settings incomplete; submission stored only in logs.")
        return {
            "status": "error",
            "message": "Email delivery is temporarily unavailable. Please try again shortly.",
        }, 503

    if mailer is None or not mailer.is_configured:
        app.logger.error("Project requirements submission attempted without a configured mailer.")
        return {
            "status": "error",
            "message": "Email delivery is temporarily unavailable. Please try again shortly.",
        }, 503

    admin_sent = _send_dynamic_email_safe(
        context="project requirements admin notification",
        recipient=MAIL_SETTINGS.requirements_recipient,
        template_id=MAIL_SETTINGS.requirements_template_id,
        dynamic_data=safe_data,
        reply_to=safe_data["email"],
    )

    client_sent = _send_dynamic_email_safe(
        context="project requirements client confirmation",
        recipient=safe_data["email"],
        template_id=MAIL_SETTINGS.requirements_template_id,
        dynamic_data=safe_data,
    )

    if admin_sent and client_sent:
        app.logger.info("Project requirements submission processed for %s", safe_data["email"])
        return {
            "status": "success",
            "message": "Requirements submitted successfully.",
            "estimate": {
                "development_rate": safe_data["development_rate"],
                "estimated_hours": safe_data["estimated_hours"],
                "development_total": safe_data["development_estimate"],
                "maintenance_total": safe_data["maintenance_estimate"],
                "page_count": safe_data["page_count"],
            },
        }

    app.logger.error(
        "Project requirements submission encountered an email delivery issue for %s (admin_sent=%s, client_sent=%s)",
        safe_data["email"],
        admin_sent,
        client_sent,
    )
    return {
        "status": "warning",
        "message": "Your request was received but email notifications could not be sent. We will contact you shortly.",
    }, 202


@app.route("/pricing")
def pricing():
    rate = current_rate()
    return render_template(
        "pricing.html",
        development_rate=format_currency(rate),
        rate_decimal=rate,
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/portfolio")
def portfolio():
    return render_template("portfolio.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        token = request.form.get("form_token")
        honeypot_value = request.form.get("company")
        is_valid, validation_message = _validate_contact_form_submission(
            token=token,
            honeypot_value=honeypot_value,
        )

        if not is_valid:
            flash(validation_message or "We could not verify your submission. Please try again.")
            session.pop(CONTACT_FORM_TOKEN_SESSION_KEY, None)
            session.pop(CONTACT_FORM_TIME_SESSION_KEY, None)
            return redirect(url_for("contact"))

        captcha_response = request.form.get("h-captcha-response")
        remote_addr = request.headers.get("X-Forwarded-For", request.remote_addr)
        captcha_valid, captcha_message = _verify_hcaptcha(captcha_response, remote_addr)

        if not captcha_valid:
            flash(captcha_message or "CAPTCHA verification failed. Please try again.")
            session.pop(CONTACT_FORM_TOKEN_SESSION_KEY, None)
            session.pop(CONTACT_FORM_TIME_SESSION_KEY, None)
            return redirect(url_for("contact"))

        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        message_body = (request.form.get("message") or "").strip()
        consent = request.form.get("consent")

        if not (name and email and phone and message_body and consent):
            flash("Please fill out all fields and provide consent.")
            return redirect(url_for("contact"))

        if len(message_body) < CONTACT_FORM_MIN_MESSAGE_LENGTH:
            flash("Please include a little more detail in your message so we can assist effectively.")
            return redirect(url_for("contact"))

        safe_name = escape(name)
        safe_email = escape(email)
        safe_phone = escape(phone)
        safe_message = escape(message_body).replace("\n", "<br>")

        email_body = (
            f"<p><strong>Name:</strong> {safe_name}</p>"
            f"<p><strong>Email:</strong> {safe_email}</p>"
            f"<p><strong>Phone:</strong> {safe_phone}</p>"
            f"<p><strong>Message:</strong><br>{safe_message}</p>"
        )

        if mailer is None or not mailer.is_configured:
            app.logger.error("Contact form submission attempted without an operational mailer.")
            flash("Email delivery is temporarily unavailable. Please try again later.")
            return redirect(url_for("contact"))

        if not MAIL_SETTINGS.owner_recipient:
            app.logger.error("MAIL_OWNER_RECIPIENT is not configured; unable to route contact submissions.")
            flash("Message captured but routing is misconfigured. We will reach out soon.")
            return redirect(url_for("contact"))

        submission_time = datetime.now(timezone.utc)

        if _send_html_email_safe(
            context="contact form notification",
            subject=f"New Contact Form Submission from {safe_name}",
            recipients=[MAIL_SETTINGS.owner_recipient],
            html_body=email_body,
            reply_to=email,
        ):
            flash("Thank you for getting in touch. Your message has been sent.")
        else:
            fallback_contact = MAIL_SETTINGS.fallback_contact_email or "our support team"
            flash(
                "Sorry, there was an error sending your message. Please try again later or contact "
                f"{fallback_contact}."
            )
        session[CONTACT_FORM_LAST_SUBMISSION_KEY] = submission_time.timestamp()
        session.pop(CONTACT_FORM_TOKEN_SESSION_KEY, None)
        session.pop(CONTACT_FORM_TIME_SESSION_KEY, None)
        return redirect(url_for("contact"))

    return render_template(
        "contact.html",
        form_token=_issue_contact_form_token(),
        captcha_site_key=CAPTCHA_SETTINGS.site_key,
    )


if __name__ == "__main__":
    import argparse

    default_host = os.getenv("HOST", "0.0.0.0")
    default_port = int(os.getenv("PORT", "8080"))

    parser = argparse.ArgumentParser(description="Run Palmertech Flask app.")
    parser.add_argument("--host", default=default_host, help="Host to run the server on")
    parser.add_argument("--port", type=int, default=default_port, help="Port to run the server on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    host = args.host
    port = args.port

    app.logger.info("Starting Flask app on %s:%s (debug=%s)", host, port, args.debug)

    if args.debug:
        import uvicorn

        uvicorn.run("app:asgi_app", host=host, port=port, reload=True)
    else:
        import uvicorn

        uvicorn.run(asgi_app, host=host, port=port)
