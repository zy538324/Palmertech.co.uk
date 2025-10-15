from itsdangerous import URLSafeSerializer
import smtplib
from email.message import EmailMessage

# CONFIGURATION
SECRET_KEY = 'replace-with-a-secure-key'  # Use your actual app.secret_key
SMTP_SERVER = 'smtp.office365.com'
SMTP_PORT = 25
SMTP_USERNAME = 'contact@palmertech.co.uk'
SMTP_PASSWORD = 'nkcgmvdwcnmnlmtz'
SENDER = 'contact@palmertech.co.uk'

# USER INPUT
recipient = input('Enter customer email: ')

# Generate token and link
s = URLSafeSerializer(SECRET_KEY)
token = s.dumps({'purpose': 'enquiry'})
link = f'http://palmertech.co.uk/enquiry/{token}'

# Compose email
msg = EmailMessage()
msg['Subject'] = 'Your Private Palmertech Project Enquiry Link'
msg['From'] = SENDER
msg['To'] = recipient
msg.set_content(f"Hello,\n\nPlease use the following private link to submit your project enquiry:\n{link}\n\nThis link is for one-time use only.\n\nBest regards,\nPalmertech")

# Send email
try:
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
    print(f"Enquiry link sent to {recipient}: {link}")
except Exception as e:
    print(f"Error sending email: {e}")
