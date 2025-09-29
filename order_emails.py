import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# ================= LOAD ENV =================
load_dotenv()
SENDER_EMAIL = os.getenv("EMAIL_USER")       # Gmail email
SENDER_PASS = os.getenv("EMAIL_PASS")        # Gmail App Password
SHOP_NAME = "AyuHealth"
SHOP_WEBSITE = "https://ayuhealth.onrender.com"

# ---------- Build Email Template ----------
def build_order_email(customer_name, cart_html, status):
    """Build an HTML order email with a human touch and a mini life lesson."""
    
    if status == "Confirmed":
        title = "✅ Your Order has been Confirmed"
        message = (
            f"Hi {customer_name}, your order has been confirmed! "
            "Just like every small step leads to big progress, confirming your order "
            "is the first step towards a delightful experience. Patience and care go a long way!"
        )
        color = "#2196f3"

    elif status.startswith("Pending"):
        reason = status.replace("Pending:", "").strip()
        title = "⚠️ Your Order is Pending"
        message = (
            f"Your order is currently pending due to: {reason}. "
            "Sometimes things don't go as planned, but challenges are opportunities in disguise. "
            "We’ll notify you as soon as your order is ready!"
        )
        color = "#ff9800"

    elif status == "Cancelled":
        title = "❌ Your Order has been Cancelled"
        message = (
            "We’re sorry, but your order was cancelled. "
            "Remember, every setback is a setup for a comeback. "
            "Feel free to reach out, and we’ll help you place a new order quickly!"
        )
        color = "#f44336"

    elif status == "Completed":
        title = "🎉 Your Order has been Delivered"
        message = (
            "Your order has been successfully delivered! "
            "Just like seeds grow into beautiful plants with care, your support allows us to grow. "
            "We hope your purchase brings joy and value!"
        )
        color = "#4caf50"

    else:
        title = "ℹ️ Order Status Update"
        message = (
            f"Hello {customer_name}, your order status is now: {status}. "
            "Remember, consistency and mindfulness turn ordinary moments into extraordinary ones!"
        )
        color = "#2196f3"

    # HTML email template
    return f"""<html>
    <body style="font-family: Arial, sans-serif; background:#f5f5f5; padding:20px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <tr>
          <td style="background:{color};padding:20px;text-align:center;color:white;font-size:20px;">
            {title}
          </td>
        </tr>
        <tr>
          <td style="padding:20px;">
            <p>{message}</p>

            <h3 style="margin-top:20px;">🛒 Your Order Details</h3>
            <table width="100%" border="1" cellspacing="0" cellpadding="8" style="border-collapse:collapse;">
              <tr style="background:#f0f0f0;">
                <th>Product & Quantity</th>
              </tr>
              {cart_html}
            </table>

            <p style="margin-top:20px;">Thank you for trusting <b>{SHOP_NAME}</b>!<br>
            Visit us anytime: <a href="{SHOP_WEBSITE}">{SHOP_WEBSITE}</a></p>
          </td>
        </tr>
        <tr>
          <td style="background:#333;color:white;text-align:center;padding:10px;font-size:12px;">
            <br>{SHOP_NAME} | <a href="{SHOP_WEBSITE}" style="color:white;">{SHOP_WEBSITE}</a>
          </td>
        </tr>
      </table>
    </body>
    </html>"""

# ---------- Format Product Summary ----------
def format_product_summary_as_html(product_summary):
    return f"<tr><td>{product_summary}</td></tr>"

# ---------- Send Email ----------
def send_email(to, subject, html_body):
    if not SENDER_EMAIL or not SENDER_PASS:
        print("❌ Missing EMAIL_USER or EMAIL_PASS in .env")
        return False

    if not to:
        print("❌ No recipient email provided")
        return False

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.send_message(msg)
        print(f"✅ Email sent to {to}")
        return True
    except Exception as e:
        print(f"❌ Email sending failed: {e}")
        return False

# ---------- Notify Customer ----------
def notify_customer(order_data, status):
    customer_info = order_data.get("customer", {})
    customer_name = customer_info.get("name", "Customer")
    customer_email = customer_info.get("email")

    if not customer_email:
        return False, "No customer email found"

    # Build product summary
    products = order_data.get("products", [])
    if not products:
        products = [{"name": "No products found", "qty": 0, "price": 0}]

    cart_html = ""
    for p in products:
        name = p.get("name", "Unknown")
        qty = p.get("qty", p.get("quantity", 1))
        price = p.get("price", 0)
        cart_html += f"<tr><td>{name} (x{qty}) - ₹{qty*price}</td></tr>"

    # Build email template
    html_body = build_order_email(customer_name, cart_html, status)

    ok = send_email(customer_email, f"Order Update from {SHOP_NAME}", html_body)
    if not ok:
        return False, f"Failed to send email to {customer_email}"

    return True, f"Email sent to {customer_email}"

