from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import os, json, ssl, smtplib, requests
from datetime import datetime
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import check_password_hash
from firebase_admin import firestore
from firebase_config import db  # Your Firebase config
from order_emails import notify_customer  # Your email helper
from auth import auth  # <-- Import the auth blueprint

# ================= LOAD ENV =================
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

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

# ================= CHECKOUT & REVIEWS LOGIC =================
# Keep your existing place_order, reviews, admin dashboard, update_order routes here
# These routes now use session['customer'] for logged-in users

# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)
