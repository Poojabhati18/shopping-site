import smtplib
from flask_mail import Message
from flask import current_app

def safe_send_mail(subject, recipients, body=None, html_body=None):
    """
    Send an email safely using Flask-Mail.

    Args:
        subject (str): Email subject.
        recipients (list): List of recipient emails.
        body (str, optional): Plain text body.
        html_body (str, optional): HTML body.
    """
    try:
        mail = current_app.extensions.get('mail')
        if not mail:
            print("❌ Flask-Mail not initialized.")
            return False

        msg = Message(subject, recipients=recipients)

        if html_body:
            msg.html = html_body
        elif body:
            msg.body = body
        else:
            msg.body = "No content provided."

        mail.send(msg)
        print(f"✅ Email sent to {recipients}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("❌ Invalid Gmail App Password or blocked account.")
    except Exception as e:
        print("❌ Email sending failed:", e)
    return False
