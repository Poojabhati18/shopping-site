import smtplib
from flask_mail import Message
from flask import current_app

def safe_send_mail(subject, recipients, body):
    try:
        mail = current_app.extensions.get('mail')
        if not mail:
            print("❌ Flask-Mail not initialized.")
            return False
        msg = Message(subject, recipients=recipients)
        msg.body = body
        mail.send(msg)
        print(f"✅ Email sent to {recipients}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ Invalid Gmail App Password or blocked account.")
    except Exception as e:
        print("❌ Email sending failed:", e)
    return False
