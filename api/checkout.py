import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("haeaorstheqpgudv")
TO_EMAIL = "digvijaybhati33@gmail.com"

def handler(request, response):
    try:
        data = json.loads(request.body)
        name = data.get("name")
        phone = data.get("phone")
        email = data.get("email")
        address = data.get("address")
        pincode = data.get("pincode")
        product = data.get("product")

        if not all([name, phone, email, address, pincode, product]):
            response.status_code = 400
            response.send({"success": False, "message": "Missing required fields"})
            return

        subject = f"🛒 New Order: {product}"
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = EMAIL_USER
        message["To"] = TO_EMAIL

        html = f"""
        <html>
          <body>
            <h2>New Order Received</h2>
            <p><strong>Product:</strong> {product}</p>
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Phone:</strong> {phone}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Address:</strong> {address}</p>
            <p><strong>Pincode:</strong> {pincode}</p>
          </body>
        </html>
        """
        message.attach(MIMEText(html, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, TO_EMAIL, message.as_string())

        response.status_code = 200
        response.send({"success": True, "message": "Order placed successfully!"})

    except Exception as e:
        response.status_code = 500
        response.send({"success": False, "message": str(e)})
