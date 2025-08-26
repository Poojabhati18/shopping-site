import smtplib
from email.mime.text import MIMEText

# ⚡ CONFIGURE THIS
SENDER_EMAIL = "elementsofvita@gmail.com"
SENDER_PASS = "clypdjyejytbytec"  # Use App Password (not Gmail password)
SHOP_NAME = "AyuHealth"
SHOP_WEBSITE = "https://ayuhealth.onrender.com"

# ---------- Build Email Template ----------
def build_order_email(customer_name, cart_html, status):
    if status == "Completed":
        title = "✅ Your Order has been Confirmed"
        message = "Thank you for shopping with us! Your order is now confirmed."
        color = "#4caf50"
    elif status == "Cancelled":
        title = "❌ Your Order has been Cancelled"
        message = "We’re sorry, but your order was cancelled. Please contact us from our website for support."
        color = "#f44336"
    else:
        title = "ℹ️ Order Status Updated"
        message = f"Your order status is now: {status}"
        color = "#ff9800"

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; background:#f5f5f5; padding:20px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <tr>
          <td style="background:{color};padding:20px;text-align:center;color:white;font-size:20px;">
            {title}
          </td>
        </tr>
        <tr>
          <td style="padding:20px;">
            <p>Hi <b>{customer_name}</b>,</p>
            <p>{message}</p>

            <h3 style="margin-top:20px;">🛒 Order Details</h3>
            <table width="100%" border="1" cellspacing="0" cellpadding="8" style="border-collapse:collapse;">
              <tr style="background:#f0f0f0;">
                <th>Product & Quantity</th>
              </tr>
              {cart_html}
            </table>

            <p style="margin-top:20px;">Best regards,<br><b>{SHOP_NAME} Team</b></p>
          </td>
        </tr>
        <tr>
          <td style="background:#333;color:white;text-align:center;padding:10px;font-size:12px;">
            <br>{SHOP_NAME} | <a href="{SHOP_WEBSITE}" style="color:white;">{SHOP_WEBSITE}</a>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

# ---------- Format Product Summary ----------
def format_product_summary_as_html(product_summary):
    # If product_summary is a string like "Cough Neel (x1) - ₹214", we put it in a single table row
    return f"<tr><td>{product_summary}</td></tr>"

# ---------- Send Email ----------
def send_email(to, subject, html_body):
    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASS)
        server.send_message(msg)

# ---------- Main function to call ----------
def notify_customer(order_data, status):
    # 1️⃣ Extract customer info from nested dict
    customer_info = order_data.get("customer", {})
    customer_name = customer_info.get("name", "Customer")
    customer_email = customer_info.get("email")

    if not customer_email:
        return False, "No customer email found"

    # 2️⃣ Build product summary HTML from products array
    products = order_data.get("products", [])
    if not products:
        products = [{"name": "No products found", "qty": 0, "price": 0}]

    cart_html = ""
    for p in products:
        name = p.get("name", "Unknown")
        qty = p.get("qty", 1)
        price = p.get("price", 0)
        cart_html += f"<tr><td>{name} (x{qty}) - ₹{qty*price}</td></tr>"

    # 3️⃣ Build and send email
    html_body = build_order_email(customer_name, cart_html, status)
    send_email(customer_email, f"Order Update from {SHOP_NAME}", html_body)

    return True, f"Email sent to {customer_email}"
