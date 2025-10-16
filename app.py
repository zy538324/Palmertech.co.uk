
from asgiref.wsgi import WsgiToAsgi
from flask import Flask, render_template, request, redirect, url_for, flash
import uvicorn
from dotenv import load_dotenv
from itsdangerous import URLSafeSerializer
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from markupsafe import escape
import base64
import io
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import requests
import shutil
from datetime import datetime

load_dotenv()
app = Flask(__name__)
asgi_app = WsgiToAsgi(app)

# --- Logging Setup ---
LOGDIR = os.path.join(os.path.dirname(__file__), 'logs')
ARCHIVEDIR = os.path.join(os.path.dirname(__file__), 'log_archive')
os.makedirs(LOGDIR, exist_ok=True)
os.makedirs(ARCHIVEDIR, exist_ok=True)
LOGFILE = os.path.join(LOGDIR, 'flask.log')

# TimedRotatingFileHandler: rotates daily, keeps 30 backups
handler = TimedRotatingFileHandler(LOGFILE, when='midnight', backupCount=30, encoding='utf-8')
handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s'))
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Archive logs older than 30 days at the start of each month
def archive_old_logs():
    today = datetime.today()
    if today.day == 1:
        for fname in os.listdir(LOGDIR):
            if fname.startswith('flask.log.'):
                fpath = os.path.join(LOGDIR, fname)
                zipname = os.path.join(ARCHIVEDIR, fname + '.zip')
                shutil.make_archive(zipname.replace('.zip',''), 'zip', LOGDIR, fname)
                os.remove(fpath)
archive_old_logs()
app.secret_key = os.getenv('SECRET_KEY')

SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'no-reply@palmertech.co.uk')
MAIL_OWNER_RECIPIENT = os.getenv('MAIL_OWNER_RECIPIENT', 'contact@palmertech.co.uk')
PALMERTECH_REQUIREMENTS_TEMPLATE_ID = os.getenv('PALMERTECH_REQUIREMENTS_TEMPLATE_ID')
PALMERTECH_REQUIREMENTS_RECIPIENT = os.getenv('PALMERTECH_REQUIREMENTS_RECIPIENT', 'projects@palmertech.co.uk')

if not SENDGRID_API_KEY:
    app.logger.warning('SENDGRID_API_KEY not configured; email features disabled.')


def send_email_via_sendgrid(subject, recipients, html_body, attachments=None, reply_to=None):
    """Send an email using SendGrid's v3 API."""
    if not SENDGRID_API_KEY:
        app.logger.error('SendGrid key missing; cannot send email.')
        return False


def send_dynamic_template_email(recipient, template_id, dynamic_data, reply_to=None):
    """Send a transactional email using a dynamic SendGrid template."""
    if not SENDGRID_API_KEY:
        app.logger.error('SendGrid key missing; cannot send dynamic template email.')
        return False

    if not template_id:
        app.logger.error('Template ID missing; cannot send dynamic template email.')
        return False

    payload = {
        'personalizations': [
            {
                'to': [{'email': recipient}],
                'dynamic_template_data': dynamic_data,
            }
        ],
        'from': {'email': MAIL_DEFAULT_SENDER, 'name': 'Palmertech Web Team'},
        'template_id': template_id,
    }

    if reply_to:
        payload['reply_to'] = {'email': reply_to}

    headers = {
        'Authorization': f'Bearer {SENDGRID_API_KEY}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post('https://api.sendgrid.com/v3/mail/send', json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        app.logger.error('Error sending dynamic template email via SendGrid: %s', exc)
        if getattr(exc, 'response', None) is not None:
            app.logger.error('SendGrid response: %s', exc.response.text)
        return False

    payload = {
        'personalizations': [
            {
                'to': [{'email': address} for address in recipients],
            }
        ],
        'from': {'email': MAIL_DEFAULT_SENDER, 'name': 'Palmertech'},
        'subject': subject,
        'content': [
            {
                'type': 'text/html',
                'value': html_body
            }
        ]
    }

    if reply_to:
        payload['reply_to'] = {'email': reply_to}

    if attachments:
        payload['attachments'] = attachments

    headers = {
        'Authorization': f'Bearer {SENDGRID_API_KEY}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post('https://api.sendgrid.com/v3/mail/send', json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        app.logger.error('Error sending email via SendGrid: %s', exc)
        if getattr(exc, 'response', None) is not None:
            app.logger.error('SendGrid response: %s', exc.response.text)
        return False

def generate_enquiry_pdf(data):
    app.logger.info('Generating enquiry PDF')
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    # Add logo at the top
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')
    if os.path.exists(logo_path):
        p.drawImage(logo_path, 50, 700, width=120, height=100, preserveAspectRatio=True, mask='auto')
        y = 680
    else:
        y = 750
    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, y + 40, "Palmertech Project Enquiry")
    p.setFont("Helvetica", 12)
    y -= 30
    for key, value in data.items():
        p.drawString(50, y, f"{key}: {value}")
        y -= 25
    p.save()
    buffer.seek(0)
    return buffer


@app.route('/enquiry/<token>', methods=['GET', 'POST'])
def private_enquiry(token):
    s = URLSafeSerializer(app.secret_key)
    try:
        data = s.loads(token)
        app.logger.info(f'Private enquiry accessed: {data}')
    except Exception:
        flash('Invalid or expired link.')
        return redirect(url_for('home'))
    if request.method == 'POST':
        form_data = {k: request.form.get(k) for k in request.form}
        pdf = generate_enquiry_pdf(form_data)
        pdf_bytes = pdf.read()
        encoded_pdf = base64.b64encode(pdf_bytes).decode('ascii')
        pdf_attachment = [{
            'content': encoded_pdf,
            'type': 'application/pdf',
            'filename': 'enquiry.pdf',
            'disposition': 'attachment'
        }]

        owner_email_sent = send_email_via_sendgrid(
            subject=f"New Project Enquiry from {form_data.get('name')}",
            recipients=[MAIL_OWNER_RECIPIENT],
            html_body='<p>Project enquiry attached.</p>',
            attachments=pdf_attachment,
            reply_to=form_data.get('email')
        )

        customer_email_sent = send_email_via_sendgrid(
            subject='Your Palmertech Project Enquiry Receipt',
            recipients=[form_data.get('email')],
            html_body='<p>Thank you for your enquiry! Please find your submitted details attached as a PDF. We will be in touch soon.</p>',
            attachments=pdf_attachment
        )

        if owner_email_sent and customer_email_sent:
            flash('Your enquiry has been submitted and emailed to you and Palmertech.')
        else:
            flash('Enquiry received, but confirmation emails could not be sent. We will follow up shortly.')
        return redirect(url_for('home'))
    return render_template('enquiry_form.html')




# Individual service pages
@app.route('/services/web-mobile')
def services_web_mobile():
    return render_template('services_web_mobile.html')

@app.route('/services/api')
def services_api():
    return render_template('services_api.html')

@app.route('/services/php-html-css-js')
def services_php_html_css_js():
    return render_template('services_php_html_css_js.html')

@app.route('/services/support')
def services_support():
    return render_template('services_support.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/testimonials')
def testimonials():
    return render_template('testimonials.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')


@app.route('/project-requirements', methods=['GET'])
def project_requirements():
    """Render the private project requirements intake form."""
    return render_template('project_requirements.html')


@app.post('/api/palmertech/requirements')
def submit_requirements():
    """Accept and forward confidential project requirement submissions."""
    required_fields = ('name', 'email', 'project_type', 'requirements')
    form_data = {field: (request.form.get(field) or '').strip() for field in request.form}

    missing = [field for field in required_fields if not form_data.get(field)]
    if missing:
        app.logger.warning('Project requirements submission missing fields: %s', ', '.join(missing))
        return {
            'status': 'error',
            'message': 'Please complete all required fields before submitting the form.',
        }, 400

    safe_data = {
        'name': str(escape(form_data.get('name', ''))),
        'email': str(escape(form_data.get('email', ''))),
        'company': str(escape(form_data.get('company', ''))),
        'project_type': str(escape(form_data.get('project_type', ''))),
        'budget': str(escape(form_data.get('budget', ''))),
        'timeline': str(escape(form_data.get('timeline', ''))),
        'requirements': str(escape(form_data.get('requirements', ''))),
        'year': str(datetime.utcnow().year),
    }

    admin_email = PALMERTECH_REQUIREMENTS_RECIPIENT

    admin_sent = send_dynamic_template_email(
        recipient=admin_email,
        template_id=PALMERTECH_REQUIREMENTS_TEMPLATE_ID,
        dynamic_data=safe_data,
        reply_to=safe_data['email'],
    )

    client_sent = send_dynamic_template_email(
        recipient=safe_data['email'],
        template_id=PALMERTECH_REQUIREMENTS_TEMPLATE_ID,
        dynamic_data=safe_data,
    )

    if admin_sent and client_sent:
        app.logger.info('Project requirements submission processed for %s', safe_data['email'])
        return {
            'status': 'success',
            'message': 'Requirements submitted successfully.',
        }

    app.logger.error(
        'Project requirements submission encountered an email delivery issue for %s (admin_sent=%s, client_sent=%s)',
        safe_data['email'],
        admin_sent,
        client_sent,
    )
    return {
        'status': 'warning',
        'message': 'Your request was received but email notifications could not be sent. We will contact you shortly.',
    }, 202

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message_body = request.form.get('message')
        consent = request.form.get('consent')
        if not (name and email and phone and message_body and consent):
            flash('Please fill out all fields and give consent.')
            return redirect(url_for('contact'))
        # Send email
        safe_name = escape(name)
        safe_email = escape(email)
        safe_phone = escape(phone)
        safe_message = escape(message_body).replace('\n', '<br>')

        email_body = (
            f"<p><strong>Name:</strong> {safe_name}</p>"
            f"<p><strong>Email:</strong> {safe_email}</p>"
            f"<p><strong>Phone:</strong> {safe_phone}</p>"
            f"<p><strong>Message:</strong><br>{safe_message}</p>"
        )

        if send_email_via_sendgrid(
            subject=f"New Contact Form Submission from {name}",
            recipients=[MAIL_OWNER_RECIPIENT],
            html_body=email_body,
            reply_to=email
        ):
            flash('Thank you for getting in touch! Your message has been sent.')
        else:
            flash('Sorry, there was an error sending your message. Please try again later.')
        return redirect(url_for('contact'))
    return render_template('contact.html')


if __name__ == '__main__':
    import argparse
    default_host = os.getenv('HOST', '0.0.0.0')
    default_port = int(os.getenv('PORT', '8080'))
    parser = argparse.ArgumentParser(description='Run Palmertech Flask app.')
    parser.add_argument('--host', default=default_host, help='Host to run the server on')
    parser.add_argument('--port', type=int, default=default_port, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    host = args.host
    port = args.port
    app.logger.info(f'Starting Flask app on {host}:{port} (debug={args.debug})')
    if args.debug:
        uvicorn.run('app:asgi_app', host=host, port=port, reload=True)
    else:
        uvicorn.run(asgi_app, host=host, port=port)
