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

        # Optional: notify admin
        try:
            add_admin_notification(
                "review_new",
                f"New review for product {product_id} ({rating}★)",
                related_id=str(product_id),
            )
        except Exception as _:
            pass

        return jsonify({"success": True}), 200
    except Exception as e:
        print("POST review error:", e)
        return jsonify({"success": False, "message": "Failed to save review."}), 500

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
        order_data = {
            "customer": {
                "name": data.get("name"),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "address": data.get("address"),
                "city": data.get("city"),
                "pincode": data.get("pincode"),
            },
            "products": data.get("products"),
            "status": "pending",  # <-- use consistent field name
            "timestamp": firestore.SERVER_TIMESTAMP
        }

        db.collection("orders").add(order_data)

        # Optional: notify customer by email
        try:
            notify_customer(customer.get("email"), order_data)
        except Exception as e:
            print("Email notify error:", e)

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
            "timestamp", direction=firestore.Query.DESCENDING
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
            "timestamp", direction=firestore.Query.DESCENDING
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

    if status.lower() == "cancelled":
        # delete or just update status? safer: update status instead of delete
        order_ref.update({"status": "cancelled"})
    else:
        order_ref.update({"status": status})

    # Notify customer
    try:
        success, msg = notify_customer(order_data, status)
    except Exception as e:
        print("Notify error:", e)
        success, msg = True, "Order updated but email failed."

    return jsonify({"success": success, "message": msg})

# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)
