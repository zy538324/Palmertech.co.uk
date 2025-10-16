"""Palmertech website WSGI application."""
from __future__ import annotations

import base64
import io
import logging
import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from itsdangerous import URLSafeSerializer
from markupsafe import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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

    return render_template("project_requirements.html")


@app.post("/api/palmertech/requirements")
def submit_requirements():
    """Accept and forward confidential project requirement submissions."""

    required_fields = ("name", "email", "project_type", "requirements")
    form_data = {field: (request.form.get(field) or "").strip() for field in request.form}

    missing = [field for field in required_fields if not form_data.get(field)]
    if missing:
        app.logger.warning("Project requirements submission missing fields: %s", ", ".join(missing))
        return {
            "status": "error",
            "message": "Please complete all required fields before submitting the form.",
        }, 400

    safe_data = {
        "name": str(escape(form_data.get("name", ""))),
        "email": str(escape(form_data.get("email", ""))),
        "company": str(escape(form_data.get("company", ""))),
        "project_type": str(escape(form_data.get("project_type", ""))),
        "budget": str(escape(form_data.get("budget", ""))),
        "timeline": str(escape(form_data.get("timeline", ""))),
        "requirements": str(escape(form_data.get("requirements", ""))),
        "year": str(datetime.utcnow().year),
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
    return render_template("pricing.html")


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
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        message_body = request.form.get("message")
        consent = request.form.get("consent")

        if not (name and email and phone and message_body and consent):
            flash("Please fill out all fields and provide consent.")
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

        if _send_html_email_safe(
            context="contact form notification",
            subject=f"New Contact Form Submission from {name}",
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
        return redirect(url_for("contact"))

    return render_template("contact.html")


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
