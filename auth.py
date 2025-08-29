from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from firebase_config import db  # Your initialized Firestore
from datetime import datetime
import re
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app
from flask_mail import Message
from app import mail, app   # <-- Import Flask-Mail instance & app

auth = Blueprint('auth', __name__)

# ================= TOKEN GENERATOR =================
s = URLSafeTimedSerializer(app.secret_key)

# ================= CONTEXT PROCESSOR =================
@auth.app_context_processor
def inject_customer():
    """Make logged-in customer available in all templates as 'customer'"""
    return dict(customer=session.get('customer'))

# ================= ROUTE PROTECTION DECORATOR =================
def login_required(f):
    """Decorator to protect routes for logged-in customers"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('customer'):
            return redirect(url_for('auth.login_customer'))
        return f(*args, **kwargs)
    return decorated

# ================= SIGNUP WITH EMAIL VERIFICATION =================
@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        agree = request.form.get('agree')

        if not all([name, email, password, confirm_password, agree]):
            return render_template('signup.html', error="Please fill all fields and agree to terms")

        # ✅ Validate email format
        email_regex = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        if not re.match(email_regex, email):
            return render_template('signup.html', error="Invalid email address. Please enter a valid one.")

        # ✅ Check if email already exists
        existing_email = db.collection('customers').where('email', '==', email).get()
        if existing_email:
            return render_template('signup.html', error="Email already registered. Please login.")

        # ✅ Check if username already exists
        existing_name = db.collection('customers').where('name', '==', name).get()
        if existing_name:
            return render_template('signup.html', error="Username already taken. Please choose another.")

        # ✅ Check password match
        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match.")

        # Hash password
        hashed_password = generate_password_hash(password)

        # Save unverified account
        customer_ref = db.collection('customers').document()
        customer_ref.set({
            'name': name,
            'email': email,
            'password': hashed_password,
            'verified': False,
            'date_created': str(datetime.now())
        })

        # Generate token
        token = s.dumps(email, salt="email-confirm")

        # Verification link
        verify_url = url_for('auth.verify_email', token=token, _external=True)

        # Send verification email
        msg = Message("Verify Your Email - AyuHealth", recipients=[email])
        msg.body = f"Hello {name},\n\nPlease click the link to verify your account:\n{verify_url}\n\nIf you didn’t request this, ignore this email."
        try:
            mail.send(msg)
        except Exception as e:
            print("Email send error:", e)

        flash("Account created! Please check your email to verify your account.", "info")
        return redirect(url_for('auth.login_customer'))

    # GET request
    return render_template('signup.html')

# ================= VERIFY EMAIL =================
@auth.route('/verify_email/<token>')
def verify_email(token):
    try:
        email = s.loads(token, salt="email-confirm", max_age=3600)  # valid for 1 hour
    except SignatureExpired:
        return "The verification link has expired.", 400
    except BadSignature:
        return "Invalid verification link.", 400

    # Mark user as verified
    users = db.collection('customers').where('email', '==', email).get()
    if not users:
        return "Account not found.", 404

    user_ref = users[0].reference
    user_ref.update({"verified": True})

    flash("Email verified successfully! You can now log in.", "success")
    return redirect(url_for('auth.login_customer'))

# ================= VERIFY EMAIL ALIAS =================
@auth.route('/verify/<token>')
def verify_email_alias(token):
    """
    Alias route for email verification:
    Allows /verify/<token> to work same as /verify_email/<token>
    """
    try:
        email = s.loads(token, salt="email-confirm", max_age=3600)  # valid for 1 hour
    except SignatureExpired:
        return "The verification link has expired.", 400
    except BadSignature:
        return "Invalid verification link.", 400

    # Mark user as verified
    users = db.collection('customers').where('email', '==', email).get()
    if not users:
        return "Account not found.", 404

    user_ref = users[0].reference
    user_ref.update({"verified": True})

    flash("Email verified successfully! You can now log in.", "success")
    return redirect(url_for('auth.login_customer'))

# ================= USERNAME CHECK =================
@auth.route('/check_username', methods=['POST'])
def check_username():
    data = request.get_json()
    username = data.get('username', '').strip()

    if not username:
        return jsonify({'available': False, 'message': 'Username cannot be empty'})

    existing_name = db.collection('customers').where('name', '==', username).get()
    if existing_name:
        return jsonify({'available': False, 'message': 'Username already taken'})
    
    return jsonify({'available': True, 'message': 'Username available'})

# ================= EMAIL CHECK =================
@auth.route('/check_email', methods=['POST'])
def check_email():
    data = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'available': False, 'message': 'Email cannot be empty'})

    existing_email = db.collection('customers').where('email', '==', email).get()
    if existing_email:
        return jsonify({'available': False, 'message': 'Email already registered'})

    return jsonify({'available': True, 'message': 'Email is available'})

# ================= LOGIN =================
@auth.route('/loginC', methods=['GET', 'POST'])
def login_customer():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        agree = request.form.get('agree')

        if not all([email, password, agree]):
            return render_template('loginC.html', error="Please fill all fields and agree to terms")

        # Fetch user from Firebase
        users = db.collection('customers').where('email', '==', email).get()
        if not users:
            return render_template('loginC.html', error="Invalid email or password")

        user_doc = users[0]
        user_data = user_doc.to_dict()

        # Check verification
        if not user_data.get('verified', False):
            return render_template('loginC.html', unverified_email=email,
                                   message="Your email is not verified. Check inbox or resend verification link.")

        # Check password
        if not check_password_hash(user_data['password'], password):
            return render_template('loginC.html', error="Invalid email or password")

        # Store user in session
        session['customer'] = {
            'id': user_doc.id,
            'name': user_data['name'],
            'email': user_data['email']
        }

        return redirect(url_for('home'))

    return render_template('loginC.html')

# ================= RESEND VERIFICATION EMAIL =================
@auth.route('/resend_verification', methods=['POST'])
def resend_verification():
    email = request.form.get('email', '').strip().lower()
    if not email:
        flash("Email is required to resend verification.", "error")
        return redirect(url_for('auth.login_customer'))

    users = db.collection('customers').where('email', '==', email).get()
    if not users:
        flash("User not found.", "error")
        return redirect(url_for('auth.login_customer'))

    user_doc = users[0]
    user_data = user_doc.to_dict()

    if user_data.get('verified', False):
        flash("Email already verified. You can log in.", "info")
        return redirect(url_for('auth.login_customer'))

    # Generate token
    token = s.dumps(email, salt="email-confirm")
    verify_url = url_for('auth.verify_email', token=token, _external=True)

    # Send verification email
    msg = Message("Verify Your Email - AyuHealth", recipients=[email])
    msg.body = f"Hello {user_data['name']},\n\nPlease click the link to verify your account:\n{verify_url}\n\nIf you didn’t request this, ignore this email."
    try:
        mail.send(msg)
        flash("Verification email resent! Please check your inbox.", "info")
    except Exception as e:
        print("Email send error:", e)
        flash("Failed to send verification email. Please try again later.", "error")

    return redirect(url_for('auth.login_customer'))

# ================= LOGOUT =================
@auth.route('/logout_customer')
def logout_customer():
    session.pop('customer', None)
    return redirect('/')
