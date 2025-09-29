from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, session, flash, abort
)
from flask_mail import Mail
from werkzeug.security import check_password_hash
from twilio.rest import Client
from dotenv import load_dotenv
from firebase_admin import firestore
from firebase_config import db  # Firebase config
from order_emails import notify_customer  # Email helper
from auth import auth  # Auth blueprint

import os, json, requests, traceback
from datetime import datetime, timezone, timedelta
import pytz

# ================= LOAD ENV =================
load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

DISABLE_CAPTCHA = os.getenv("DISABLE_CAPTCHA", "false").lower() in ("1", "true", "yes")

# ================= TWILIO CONFIG =================
ACCOUNT_SID = os.getenv("ACCOUNT_SID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
WHATSAPP_TO = os.getenv("WHATSAPP_TO")  # your WhatsApp number like whatsapp:+91XXXXXXXXXX
WHATSAPP_FROM = "whatsapp:+14155238886"  # Twilio sandbox number
twilio_client = Client(ACCOUNT_SID, AUTH_TOKEN)

# ================= FLASK-MAIL CONFIG =================
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get("EMAIL_USER"),
    MAIL_PASSWORD=os.environ.get("EMAIL_PASS"),
    MAIL_DEFAULT_SENDER=os.environ.get("EMAIL_USER"),
)
mail = Mail(app)

# ================= REGISTER BLUEPRINT =================
app.register_blueprint(auth)  # Customer auth routes (signup/login/logout)

# ================= GLOBAL CONTEXT PROCESSOR =================
@app.context_processor
def inject_customer_global():
    """Make logged-in customer available in all templates"""
    return dict(customer=session.get("customer"))

# ================= ENV VARIABLES =================
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
TO_EMAIL = os.getenv("TO_EMAIL", "elementsofvita@gmail.com")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH")  # Hashed password from .env

RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

IST = pytz.timezone("Asia/Kolkata")
OWNER_EMAIL = EMAIL_USER  # App owner

# ================= CAPTCHA VERIFY GATE =================
@app.route("/")
def root():
    if DISABLE_CAPTCHA:
        session["verified"] = True
        return redirect(url_for("home"))
    if session.get("verified"):
        return redirect(url_for("home"))
    return render_template("verify.html", site_key=RECAPTCHA_SITE_KEY)

@app.route("/verify", methods=["POST"])
def verify():
    if DISABLE_CAPTCHA:
        session["verified"] = True
        return redirect(url_for("home"))

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
try:
    with open("products.json", "r") as f:
        raw_products = json.load(f)
    PRODUCTS = [{**p, "id": str(idx)} for idx, p in enumerate(raw_products, start=1)]
except Exception as e:
    print("Error loading products.json:", e)
    PRODUCTS = []

# ================= DECORATORS =================
def require_verification(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if DISABLE_CAPTCHA:
            session["verified"] = True
            return f(*args, **kwargs)
        if not session.get("verified"):
            return redirect(url_for("root"))
        return f(*args, **kwargs)
    return wrapper

# ================= PAGES =================
@app.route("/home")
@require_verification
def home():
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

# ================= REVIEWS API =================
def _serialize_review(doc):
    data = doc.to_dict()
    ts = data.get("timestamp")
    if ts and hasattr(ts, "to_datetime"):
        data["timestamp"] = ts.to_datetime().isoformat()
    elif isinstance(ts, datetime):
        data["timestamp"] = ts.isoformat()
    else:
        data["timestamp"] = datetime.utcnow().isoformat()
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
              .order_by("timestamp", direction=firestore.Query.DESCENDING)
        )
        reviews = [_serialize_review(doc) for doc in q.stream()]
        return jsonify(reviews), 200
    except Exception as e:
        print("GET reviews error:", e)
        return jsonify([]), 200

@app.route("/api/reviews/<product_id>", methods=["POST"])
@require_verification
def post_review(product_id):
    customer = session.get("customer")
    data = request.get_json(silent=True) or {}
    rating = int(data.get("rating") or 0)
    review_text = (data.get("review") or "").strip()

    if rating < 1 or rating > 5 or len(review_text) < 10:
        return jsonify({"success": False, "message": "Invalid rating or review too short."}), 400

    try:
        payload = {
            "productId": str(product_id),
            "rating": rating,
            "review": review_text,
            "authorId": customer.get("id") if isinstance(customer, dict) else None,
            "authorName": customer.get("name") if isinstance(customer, dict) else None,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }
        db.collection("reviews").add(payload)
        return jsonify({"success": True}), 200
    except Exception as e:
        print("POST review error:", e)
        return jsonify({"success": False, "message": "Failed to save review."}), 500

# ================= ORDER PLACEMENT =================
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
        now_ist = datetime.now(IST)

        # Daily order limit (except owner)
        if customer_email != OWNER_EMAIL:
            start_of_day = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            start_of_day_utc = start_of_day.astimezone(timezone.utc)
            end_of_day_utc = end_of_day.astimezone(timezone.utc)

            orders_ref = (
                db.collection("orders")
                .where("customer.email", "==", customer_email)
                .where("timestamp", ">=", start_of_day_utc)
                .where("timestamp", "<", end_of_day_utc)
            )
            if list(orders_ref.stream()):
                return jsonify({
                    "success": False,
                    "message": "⚠️ You have already placed an order today. Please try again tomorrow after midnight (IST)."
                }), 400

        # Create order
        now_utc = datetime.now(timezone.utc)
        order_data = {
            "customer": {
                "name": data.get("name"),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "address": data.get("address"),
                "city": data.get("city"),
                "pincode": data.get("pincode"),
            },
            "products": data.get("products", []),
            "status": "pending",
            "timestamp": now_utc
        }
        db.collection("orders").add(order_data)

        # Email notification
        try:
            notify_customer(order_data, "Placed")
        except Exception as e:
            print("Email notify error:", e)

        # WhatsApp notification
        try:
            products_text = "\n".join([
                f"{p.get('name', 'Unknown')} | Qty: {int(p.get('quantity', p.get('qty', 1)))} | "
                f"Price: ₹{float(p.get('price',0))} | Total: ₹{int(p.get('quantity', p.get('qty',1)))*float(p.get('price',0))}"
                for p in order_data.get('products', [])
            ])

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

        return jsonify({"success": True, "message": "✅ Order placed successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Error placing order: {str(e)}"}), 500

# ================= ADMIN DASHBOARD =================
@app.route('/admin')
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("login"))

    orders = []
    try:
        orders_ref = db.collection("orders").order_by(
            "timestamp", direction=firestore.Query.DESCENDING
        )
        for doc in orders_ref.stream():
            order_data = doc.to_dict()
            order_data["id"] = doc.id
            order_data["customer"] = order_data.get("customer", {})
            order_data["products"] = order_data.get("products", [])
            order_data["total"] = sum(
                float(p.get("price", 0)) * int(p.get("qty", p.get("quantity", 1)))
                for p in order_data["products"]
            )
            ts = order_data.get("timestamp")
            try:
                if ts and hasattr(ts, "to_datetime"):
                    dt = ts.to_datetime().astimezone(timezone.utc)
                    order_data["created_at"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(ts, datetime):
                    dt = ts.astimezone(timezone.utc)
                    order_data["created_at"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    order_data["created_at"] = "—"
            except Exception as e:
                print("Timestamp parse error:", e)
                order_data["created_at"] = "—"
            orders.append(order_data)
    except Exception:
        traceback.print_exc()
        orders = []

    return render_template("admin.html", orders=orders)

# ================= ORDER STATUS UPDATES =================
def _update_order_status(order_id, new_status, reason=None):
    ref = db.collection("orders").document(order_id)
    doc = ref.get()
    if not doc.exists:
        return None, "Order not found."
    order = doc.to_dict()
    update_data = {"status": new_status}
    if reason:
        update_data["pending_reason"] = reason
        order["pending_reason"] = reason
    ref.update(update_data)
    order.update(update_data)
    return order, None

@app.route("/orders/<order_id>/confirm", methods=["POST"])
def confirm_order(order_id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    try:
        order, err = _update_order_status(order_id, "confirmed")
        if err:
            flash(err, "warning")
        else:
            try:
                notify_customer(order, "Confirmed")
                flash("Order confirmed and email sent.", "success")
            except Exception as e:
                flash(f"Order confirmed but email failed: {e}", "danger")
    except Exception as e:
        flash(f"Error confirming order: {e}", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route("/orders/<order_id>/cancel", methods=["POST"])
def cancel_order(order_id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    try:
        ref = db.collection("orders").document(order_id)
        doc = ref.get()
        if not doc.exists:
            flash("Order not found.", "warning")
            return redirect(url_for("admin_dashboard"))
        order = doc.to_dict()
        ref.delete()
        try:
            notify_customer(order, "Cancelled")
            flash("Order cancelled and email sent.", "success")
        except Exception as e:
            flash(f"Order cancelled but email failed: {e}", "danger")
    except Exception as e:
        flash(f"Error cancelling order: {e}", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route("/orders/<order_id>/complete", methods=["POST"])
def complete_order(order_id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    try:
        order, err = _update_order_status(order_id, "completed")
        if err:
            flash(err, "warning")
        else:
            try:
                notify_customer(order, "Completed")
                flash("Order marked as completed and email sent.", "success")
            except Exception as e:
                flash(f"Order completed but email failed: {e}", "danger")
    except Exception as e:
        flash(f"Error completing order: {e}", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route("/orders/<order_id>/pending", methods=["POST"])
def pending_order(order_id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    reason = request.form.get("reason", "No reason provided")
    try:
        order, err = _update_order_status(order_id, "pending", reason)
        if err:
            flash(err, "warning")
        else:
            try:
                notify_customer(order, f"Pending: {reason}")
                flash(f"Order marked as pending ({reason}) and email sent.", "success")
            except Exception as e:
                flash(f"Order pending but email failed: {e}", "danger")
    except Exception as e:
        flash(f"Error marking order as pending: {e}", "danger")
    return redirect(url_for("admin_dashboard"))

# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)
