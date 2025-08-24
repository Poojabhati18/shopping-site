from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import os, json, ssl, smtplib, requests
from datetime import datetime
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import check_password_hash
from firebase_admin import firestore
from firebase_config import db  # Updated Firebase config
from order_emails import notify_customer  # Your email helper

# ================= LOAD ENV =================
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

# ================= ENV VARIABLES =================
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
TO_EMAIL = os.getenv("TO_EMAIL", "digvijaybhati33@gmail.com")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH")  # Hashed password from .env

RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

REVIEWS = {}

# ================= CAPTCHA VERIFY GATE =================
@app.route("/")
def root():
    if session.get("verified"):
        return redirect(url_for("home"))
    return render_template("verify.html", site_key=RECAPTCHA_SITE_KEY)

@app.route("/verify", methods=["POST"])
def verify():
    recaptcha_response = request.form.get("g-recaptcha-response")
    if not recaptcha_response:
        return "Please complete the CAPTCHA.", 400

    # Verify with Google
    data = {"secret": RECAPTCHA_SECRET_KEY, "response": recaptcha_response}
    r = requests.post("https://www.google.com/recaptcha/api/siteverify", data=data)
    result = r.json()

    if result.get("success"):
        session["verified"] = True
        return redirect(url_for("home"))
    else:
        return "Captcha verification failed. Please try again.", 400

# ================= AUTH =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username != ADMIN_USER or not ADMIN_PASS_HASH or not check_password_hash(ADMIN_PASS_HASH, password):
            return render_template("login.html", error="Invalid credentials")

        session["admin"] = True
        return redirect(url_for("admin_dashboard"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))

# ================= LOAD PRODUCTS =================
with open("products.json", "r") as f:
    raw_products = json.load(f)

PRODUCTS = []
for index, p in enumerate(raw_products, start=1):
    PRODUCTS.append({**p, "id": str(index)})

# ================= PAGES =================
def require_verification(f):
    """Decorator to check CAPTCHA verification before accessing pages"""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("verified"):
            return redirect(url_for("root"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/home")
@require_verification
def home():
    hottest_products = []  # Optional: populate if needed
    return render_template("index.html", hottest_products=hottest_products)

@app.route("/products")
@require_verification
def products_page():
    products_with_urls = [
        {**p, "image_url": url_for("static", filename=p["image"])} for p in PRODUCTS
    ]
    return render_template("products.html", products=products_with_urls)

@app.route("/cart")
@require_verification
def cart_page():
    return render_template("cart.html")

@app.route("/checkout")
@require_verification
def checkout_page():
    return render_template("checkout.html")

@app.route("/about")
@require_verification
def about_page():
    return render_template("about.html")

@app.route("/contact")
@require_verification
def contact_page():
    return render_template("contact.html")

@app.route("/privacypolicy")
@require_verification
def privacy_page():
    return render_template("privacypolicy.html")

@app.route("/refund")
@require_verification
def refund_page():
    return render_template("refund.html")

@app.route("/shipping")
@require_verification
def shipping_page():
    return render_template("shipping.html")

@app.route("/terms")
@require_verification
def terms_page():
    return render_template("terms.html")

# ================= HELPER =================
def add_admin_notification(notification_type, message, related_id):
    try:
        db.collection("admin_notifications").add({
            "type": notification_type,
            "message": message,
            "related_id": related_id,
            "read": False,
            "timestamp": datetime.now()
        })
    except Exception as e:
        print("Error adding admin notification:", e)

# ================= CHECKOUT =================
@app.route("/place_order", methods=["POST"])
@require_verification
def place_order():
    data = request.json
    name = data.get("name")
    phone = data.get("phone")
    email = data.get("email")
    address = data.get("address")
    city = data.get("city")
    pincode = data.get("pincode")
    product = data.get("product")

    if not all([name, phone, email, address, city, pincode, product]):
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    try:
        if isinstance(product, list):
            product_summary_str = "\n".join([f"{p['name']} (x{p['qty']}) - ₹{p['qty']*p['price']}" for p in product])
        else:
            product_summary_str = str(product)

        order_ref = db.collection("orders").document()
        order_data = {
            "customer_name": name,
            "customer_email": email,
            "address": f"{address}, {city}, {pincode}",
            "product_summary": product_summary_str,
            "order_status": "Pending",
            "date_ordered": datetime.now()
        }

        order_ref.set(order_data)
        order_id = order_ref.id

        add_admin_notification(
            notification_type="new_order",
            message=f"New order #{order_id} placed by {name}",
            related_id=order_id
        )

        if EMAIL_USER and EMAIL_PASS:
            try:
                message = MIMEMultipart("alternative")
                message["Subject"] = f"🛒 New Order #{order_id}"
                message["From"] = EMAIL_USER
                message["To"] = TO_EMAIL

                html = f"""
                <html><body>
                    <h2>New Order Received</h2>
                    <p><strong>Name:</strong> {name}</p>
                    <p><strong>Phone:</strong> {phone}</p>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Address:</strong> {address}</p>
                    <p><strong>City:</strong> {city}</p>
                    <p><strong>Pincode:</strong> {pincode}</p>
                    <h3>Product Summary:</h3>
                    <pre>{product_summary_str}</pre>
                </body></html>
                """
                message.attach(MIMEText(html, "html"))
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                    server.login(EMAIL_USER, EMAIL_PASS)
                    server.sendmail(EMAIL_USER, TO_EMAIL, message.as_string())
            except Exception as email_err:
                print("Error sending email:", email_err)

        return jsonify({"success": True, "message": "Order placed successfully!"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Server error: {repr(e)}"}), 500

# ================= Notifications =================
@app.route('/admin/notifications/mark_read/<notification_id>')
def mark_notification_read(notification_id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    try:
        db.collection("admin_notifications").document(notification_id).update({"read": True})
    except Exception as e:
        print("Error marking notification as read:", e)
    return redirect(url_for("admin_dashboard"))

# ================= REVIEWS =================
@app.route("/api/reviews/<product_id>", methods=["GET"])
def get_reviews(product_id):
    return jsonify(REVIEWS.get(product_id, []))

@app.route("/api/reviews/<product_id>", methods=["POST"])
def post_review(product_id):
    data = request.json
    rating = data.get("rating")
    review_text = data.get("review")
    if not rating or not review_text:
        return jsonify({"success": False, "message": "Missing fields"}), 400
    REVIEWS.setdefault(product_id, []).append({
        "rating": rating,
        "review": review_text,
        "timestamp": datetime.now().isoformat()
    })
    return jsonify({"success": True})

# ================= ADMIN DASHBOARD =================
@app.route('/admin')
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("login"))

    # Fetch orders
    orders = []
    try:
        orders_ref = db.collection("orders").order_by(
            "date_ordered", direction=firestore.Query.DESCENDING
        )
        for doc in orders_ref.stream():
            try:
                order_data = doc.to_dict()
                order_data["id"] = doc.id
                orders.append(order_data)
            except Exception as e:
                print("Error processing order:", e)
    except Exception as e:
        print("Firebase fetch error:", e)
        orders = []

    # Fetch notifications
    notifications = []
    try:
        notifications_ref = db.collection("admin_notifications").order_by(
            "timestamp", direction=db._client.Query.DESCENDING
        )
        for n in notifications_ref.stream():
            try:
                notif = n.to_dict()
                notif["id"] = n.id
                notifications.append(notif)
            except Exception as e:
                print("Error processing notification:", e)
    except Exception as e:
        print("Firebase notifications error:", e)
        notifications = []

    return render_template("admin.html", orders=orders, notifications=notifications)

# ================= Update / Cancel Order =================
@app.route("/update_order/<order_id>/<status>", methods=["POST"])
def update_order(order_id, status):
    order_ref = db.collection("orders").document(order_id)
    order = order_ref.get()
    if not order.exists:
        return jsonify({"success": False, "error": "Order not found"}), 404

    order_data = order.to_dict()

    if status == "Cancelled":
        order_ref.delete()
    else:
        order_ref.update({"order_status": status})

    # Send email
    success, msg = notify_customer(order_data, status)
    return jsonify({"success": success, "message": msg})

# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)