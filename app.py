from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_mail import Mail, Message 
import os, json, ssl, smtplib, requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import check_password_hash
from firebase_admin import firestore
from firebase_config import db  # Your Firebase config
from order_emails import notify_customer  # Your email helper
from auth import auth  # <-- Import the auth blueprint
from twilio.rest import Client

# ================= LOAD ENV =================
load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# ================= TWILIO CONFIG =================
ACCOUNT_SID = os.getenv("ACCOUNT_SID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
WHATSAPP_TO = os.getenv("WHATSAPP_TO")  # your WhatsApp number like whatsapp:+91XXXXXXXXXX
WHATSAPP_FROM = "whatsapp:+14155238886"  # Twilio sandbox number

twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)

# ================= FLASK-MAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.environ.get("EMAIL_PASS")
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get("EMAIL_USER")

mail = Mail(app)  # <-- Initialize Flask-Mail

# ================= REGISTER BLUEPRINT =================
app.register_blueprint(auth)  # Customer auth routes (signup/login/logout)

# ================= GLOBAL CONTEXT PROCESSOR =================
@app.context_processor
def inject_customer_global():
    """Make logged-in customer available in all templates"""
    return dict(customer=session.get('customer'))

# ================= ENV VARIABLES =================
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
TO_EMAIL = os.getenv("TO_EMAIL", "elementsofvita@gmail.com")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH")  # Hashed password from .env

RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

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
    data = {"secret": RECAPTCHA_SECRET_KEY, "response": recaptcha_response}
    r = requests.post("https://www.google.com/recaptcha/api/siteverify", data=data)
    result = r.json()
    if result.get("success"):
        session["verified"] = True
        return redirect(url_for("home"))
    return "Captcha verification failed. Please try again.", 400

# ================= ADMIN AUTH =================
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
PRODUCTS = [{**p, "id": str(idx)} for idx, p in enumerate(raw_products, start=1)]

# ================= DECORATORS =================
def require_verification(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("verified"):
            return redirect(url_for("root"))
        return f(*args, **kwargs)
    return wrapper

# ================= PAGES =================
@app.route("/home")
@require_verification
def home():
    # Renders index.html which extends base.html
    return render_template("index.html", hottest_products=[])

@app.route("/products")
@require_verification
def products_page():
    products_with_urls = [{**p, "image_url": url_for("static", filename=p["image"])} for p in PRODUCTS]
    return render_template("products.html", products=products_with_urls)

@app.route("/cart")
@require_verification
def cart_page():
    if not session.get("customer"):
        return redirect(url_for("auth.login_customer"))
    return render_template("cart.html")

@app.route("/checkout")
@require_verification
def checkout_page():
    if not session.get("customer"):
        return redirect(url_for("auth.login_customer"))
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

# ================= CHECKOUT & REVIEWS LOGIC =================
# ================= REVIEWS API =================
from flask import abort
from datetime import datetime
from firebase_admin import firestore as _firestore

def _serialize_review(doc):
    data = doc.to_dict()
    ts = data.get("timestamp")
    # Firestore Timestamp -> ISO string
    if ts and hasattr(ts, "to_datetime"):
        data["timestamp"] = ts.to_datetime().isoformat()
    elif isinstance(ts, datetime):
        data["timestamp"] = ts.isoformat()
    else:
        # fallback if missing
        data["timestamp"] = datetime.utcnow().isoformat()
    # only expose fields the frontend expects
    return {
        "rating": int(data.get("rating", 0)),
        "review": data.get("review", ""),
        "timestamp": data["timestamp"],
    }

@app.route("/api/reviews/<product_id>", methods=["GET"])
@require_verification
def get_reviews(product_id):
    try:
        q = (
            db.collection("reviews")
              .where("productId", "==", str(product_id))
              .order_by("timestamp", direction=_firestore.Query.DESCENDING)
        )
        reviews = [_serialize_review(doc) for doc in q.stream()]
        return jsonify(reviews), 200
    except Exception as e:
        print("GET reviews error:", e)
        return jsonify([]), 200  # fail soft so UI still works

@app.route("/api/reviews/<product_id>", methods=["POST"])
@require_verification
def post_review(product_id):
    # Optional: require logged-in customer to post
    customer = session.get("customer")
    # If you want to force login for reviews, uncomment:
    # if not customer:
    #     return jsonify({"success": False, "message": "Please log in to review."}), 401

    data = request.get_json(silent=True) or {}
    rating = int(data.get("rating") or 0)
    review_text = (data.get("review") or "").strip()

    # Validate exactly like your front-end
    if rating < 1 or rating > 5 or len(review_text) < 10:
        return jsonify({"success": False, "message": "Invalid rating or review too short."}), 400

    try:
        payload = {
            "productId": str(product_id),
            "rating": rating,
            "review": review_text,
            # store minimal author metadata if available
            "authorId": customer.get("id") if isinstance(customer, dict) else None,
            "authorName": customer.get("name") if isinstance(customer, dict) else None,
            # Use server timestamp so ordering works reliably
            "timestamp": _firestore.SERVER_TIMESTAMP,
        }
        db.collection("reviews").add(payload)

        return jsonify({"success": True}), 200
    except Exception as e:
        print("POST review error:", e)
        return jsonify({"success": False, "message": "Failed to save review."}), 500

OWNER_EMAIL = os.environ.get("EMAIL_USER")  # reads your email from env

@app.route("/place_order", methods=["POST"])
@require_verification
def place_order():
    customer = session.get("customer")
    if not customer:
        return jsonify({"success": False, "message": "Please log in"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid data"}), 400

    try:
        customer_email = customer.get("email")
        today = datetime.now(timezone.utc).date()

        # Only enforce daily restriction for non-owner
        if customer_email != OWNER_EMAIL:
            orders_ref = db.collection("orders").where("customer.email", "==", customer_email)
            existing_orders = orders_ref.stream()
            for order in existing_orders:
                order_data_check = order.to_dict()
                if "timestamp" in order_data_check:
                    order_date = order_data_check["timestamp"].astimezone(timezone.utc).date()
                    if order_date == today:
                        return jsonify({
                            "success": False,
                            "message": "You can only place one order per day."
                        }), 400

        # Create order dict
        order_data = {
            "customer": {
                "name": data.get("name"),
                "email": customer_email,
                "phone": data.get("phone"),
                "address": data.get("address"),
                "city": data.get("city"),
                "pincode": data.get("pincode"),
            },
            "products": data.get("products", []),
            "status": "pending",
            "timestamp": firestore.SERVER_TIMESTAMP
        }

        # Save order to Firestore
        db.collection("orders").add(order_data)

        # ===== Email Notification =====
        try:
            if isinstance(order_data, dict) and isinstance(order_data.get("customer"), dict):
                notify_customer(customer_email, order_data)
            else:
                print("Email notify skipped: order_data or customer info is invalid")
        except Exception as e:
            print("Email notify error:", e)

        # ===== WhatsApp Notification =====
        try:
            products = order_data.get('products', [])
            products_text_lines = []

            for p in products:
                name = p.get('name', 'Unknown')
                qty = int(p.get('quantity', 1))
                price = float(p.get('price', 0))
                total = qty * price
                products_text_lines.append(f"{name} | Qty: {qty} | Price: ₹{price} | Total: ₹{total}")

            products_text = "\n".join(products_text_lines)

            message_text = f"""
📦 *New Order Alert!*
👤 Name: {order_data['customer'].get('name')}
📧 Email: {order_data['customer'].get('email')}
📞 Phone: {order_data['customer'].get('phone')}
🏙️ City: {order_data['customer'].get('city')}
📮 Pincode: {order_data['customer'].get('pincode')}
🏠 Address: {order_data['customer'].get('address')}

🛍️ Products:
{products_text}
"""

            twilio_client.messages.create(
                from_=WHATSAPP_FROM,
                to=WHATSAPP_TO,
                body=message_text
            )
        except Exception as e:
            print("WhatsApp notify error:", e)

        return jsonify({"success": True, "message": "Order placed successfully"}), 200

    except Exception as e:
        print("Place order error:", e)
        return jsonify({"success": False, "message": "Failed to place order"}), 500

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

# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)
