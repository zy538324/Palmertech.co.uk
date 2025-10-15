import tkinter as tk
from tkinter import messagebox
from itsdangerous import URLSafeSerializer
import smtplib
from email.message import EmailMessage

# CONFIGURATION
SECRET_KEY = 'replace-with-a-secure-key'  # Use your actual app.secret_key
SMTP_SERVER = 'smtp.office365.com'
SMTP_PORT = 587
SMTP_USERNAME = 'contact@palmertech.co.uk'
SMTP_PASSWORD = 'nkcgmvdwcnmnlmtz'
SENDER = 'contact@palmertech.co.uk'
DOMAIN = 'http://palmertech.co.uk'  # Update to your actual domain

class EnquiryApp:
    def __init__(self, root):
        self.root = root
        root.title('Palmertech Enquiry Link Generator')
        root.geometry('420x220')
        root.resizable(False, False)

        tk.Label(root, text='Customer Email:', font=('Segoe UI', 11)).pack(pady=(18, 4))
        self.email_entry = tk.Entry(root, width=40, font=('Segoe UI', 11))
        self.email_entry.pack(pady=2)

        self.send_btn = tk.Button(root, text='Send Enquiry Link', command=self.send_link, font=('Segoe UI', 11), bg='#2196f3', fg='white')
        self.send_btn.pack(pady=12)

        self.result_label = tk.Label(root, text='', font=('Segoe UI', 10), fg='red', wraplength=400, justify='left')
        self.result_label.pack(pady=2)

    def send_link(self):
        recipient = self.email_entry.get().strip()
        if not recipient:
            self.result_label.config(text='Please enter a customer email.')
            return
        try:
            s = URLSafeSerializer(SECRET_KEY)
            token = s.dumps({'purpose': 'enquiry'})
            link = f'{DOMAIN}/enquiry/{token}'

            msg = EmailMessage()
            msg['Subject'] = 'Your Private Palmertech Project Enquiry Link'
            msg['From'] = SENDER
            msg['To'] = recipient
            msg.set_content(f"Hello,\n\nPlease use the following private link to submit your project enquiry:\n{link}\n\nThis link is for one-time use only.\n\nBest regards,\nPalmertech")

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
            self.result_label.config(text=f'Enquiry link sent to {recipient}:\n{link}', fg='green')
        except Exception as e:
            self.result_label.config(text=f'Error: {e}', fg='red')

if __name__ == '__main__':
    root = tk.Tk()
    app = EnquiryApp(root)
    root.mainloop()
