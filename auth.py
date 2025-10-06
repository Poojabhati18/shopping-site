from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from firebase_config import db  # Your initialized Firestore
from datetime import datetime
import re
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_mail import Message
from email_utils import safe_send_mail

auth = Blueprint('auth', __name__)

# ================= TOKEN GENERATOR =================
s = None  # will initialize lazily to avoid circular import

def get_serializer():
    global s
    if s is None:
        s = URLSafeTimedSerializer(current_app.secret_key)
    return s

# ================= CONTEXT PROCESSOR =================
@auth.app_context_processor
def inject_customer():
    return dict(customer=session.get('customer'))

# ================= ROUTE PROTECTION DECORATOR =================
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('customer'):
            return redirect(url_for('auth.login_customer'))
        return f(*args, **kwargs)
    return decorated

# ================= SIGNUP =================
@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        agree = request.form.get('agree')

        # Validation checks
        if not all([name, email, password, confirm_password, agree]):
            return render_template('signup.html', error="Please fill all fields and agree to the terms.")

        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            return render_template('signup.html', error="Invalid email format.")

        if db.collection('customers').where('email', '==', email).get():
            return render_template('signup.html', error="Email already registered. Please login.")

        if db.collection('customers').where('name', '==', name).get():
            return render_template('signup.html', error="Username already taken. Please choose another.")

        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match.")

        # Hash password and save user
        hashed_password = generate_password_hash(password)
        db.collection('customers').document().set({
            'name': name,
            'email': email,
            'password': hashed_password,
            'verified': False,
            'date_created': str(datetime.now())
        })

        # Generate verification token
        token = get_serializer().dumps(email, salt="email-confirm")
        verify_url = url_for('auth.verify_email', token=token, _external=True)

        # ✉️ Build HTML email
        html_body = f"""
        <html>
        <body style="font-family:Arial,sans-serif;background:#f7f7f7;padding:20px;">
          <table style="max-width:600px;margin:auto;background:white;border-radius:10px;overflow:hidden;">
            <tr><td style="background:#2b4d3a;color:white;padding:20px;text-align:center;font-size:20px;">
              🌿 Welcome to AyuHealth, {name}!
            </td></tr>
            <tr><td style="padding:20px;color:#333;">
              <p>Hi <b>{name}</b>,</p>
              <p>We’re delighted to have you join the <b>AyuHealth</b> family. 
              Please verify your email address by clicking the button below:</p>
              <p style="text-align:center;margin:25px 0;">
                <a href="{verify_url}" 
                   style="background:#4caf50;color:white;text-decoration:none;padding:12px 25px;border-radius:6px;">
                   Verify My Email
                </a>
              </p>
              <p>If you didn’t create an account, please ignore this email.</p>
              <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
              <p style="font-style:italic;color:#555;">
                💭 <b>Life Tip:</b> The best investment you can ever make is in your health — 
                because every step toward wellness builds a better tomorrow.
              </p>
              <p style="margin-top:20px;">With care,<br><b>The AyuHealth Team</b></p>
            </td></tr>
            <tr><td style="background:#2b4d3a;color:white;text-align:center;padding:10px;font-size:12px;">
              © 2025 AyuHealth | <a href="https://ayuhealth.onrender.com" style="color:white;">Visit Website</a>
            </td></tr>
          </table>
        </body>
        </html>
        """

        try:
            # Safe send HTML email
            safe_send_mail(
                subject="🌿 Verify Your Email - AyuHealth",
                recipients=[email],
                html_body=html_body
            )
            flash("🎉 Account created! Please check your email to verify your account.", "success")
        except Exception as e:
            print("Email send error:", e)
            flash("Account created, but we couldn’t send the verification email. Please contact support.", "error")

        return redirect(url_for('auth.login_customer'))

    return render_template('signup.html')

# ================= VERIFY EMAIL =================
@auth.route('/verify_email/<token>')
def verify_email(token):
    try:
        email = get_serializer().loads(token, salt="email-confirm", max_age=3600)
    except SignatureExpired:
        return "The verification link has expired.", 400
    except BadSignature:
        return "Invalid verification link.", 400

    users = db.collection('customers').where('email', '==', email).get()
    if not users:
        return "Account not found.", 404

    users[0].reference.update({"verified": True})
    flash("Email verified successfully! You can now log in.", "success")
    return redirect(url_for('auth.login_customer'))

# ================= VERIFY EMAIL ALIAS =================
@auth.route('/verify/<token>')
def verify_email_alias(token):
    return verify_email(token)

# ================= USERNAME CHECK =================
@auth.route('/check_username', methods=['POST'])
def check_username():
    username = request.get_json().get('username', '').strip()
    if not username:
        return jsonify({'available': False, 'message': 'Username cannot be empty'})
    if db.collection('customers').where('name', '==', username).get():
        return jsonify({'available': False, 'message': 'Username already taken'})
    return jsonify({'available': True, 'message': 'Username available'})

# ================= EMAIL CHECK =================
@auth.route('/check_email', methods=['POST'])
def check_email():
    email = request.get_json().get('email', '').strip().lower()
    if not email:
        return jsonify({'available': False, 'message': 'Email cannot be empty'})
    if db.collection('customers').where('email', '==', email).get():
        return jsonify({'available': False, 'message': 'Email already registered'})
    return jsonify({'available': True, 'message': 'Email is available'})

# ================= LOGIN =================
@auth.route('/loginC', methods=['GET', 'POST'])
def login_customer():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        agree = request.form.get('agree')

        if not all([email, password, agree]):
            return render_template('loginC.html', error="Please fill all fields and agree to terms")

        users = db.collection('customers').where('email', '==', email).get()
        if not users:
            return render_template('loginC.html', error="Invalid email or password")

        user_data = users[0].to_dict()

        if not user_data.get('verified', False):
            return render_template('loginC.html', unverified_email=email,
                                   message="Your email is not verified. Check inbox or resend verification link.")

        if not check_password_hash(user_data['password'], password):
            return render_template('loginC.html', error="Invalid email or password")

        session['customer'] = {
            'id': users[0].id,
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

    user_data = users[0].to_dict()
    if user_data.get('verified', False):
        flash("Email already verified. You can log in.", "info")
        return redirect(url_for('auth.login_customer'))

    # ✅ use get_serializer instead of s
    token = get_serializer().dumps(email, salt="email-confirm")
    verify_url = url_for('auth.verify_email', token=token, _external=True)

    msg = Message("Verify Your Email - AyuHealth", recipients=[email])
    msg.body = f"Hello {user_data['name']},\n\nPlease click the link to verify your account:\n{verify_url}\n\nIf you didn’t request this, ignore this email."

    try:
        # ✅ use current_app.extensions['mail']
        safe_send_mail(msg.subject, msg.recipients, msg.body)
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

# ================= FORGOT PASSWORD =================
@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash("Please enter your email", "error")
            return redirect(url_for('auth.forgot_password'))

        users = db.collection('customers').where('email', '==', email).get()
        if not users:
            flash("Email not found", "error")
            return redirect(url_for('auth.forgot_password'))

        token = get_serializer().dumps(email, salt="password-reset")
        reset_url = url_for('auth.reset_password', token=token, _external=True)

        msg = Message("Reset Your Password - AyuHealth", recipients=[email])
        msg.body = f"Hello,\n\nClick the link below to reset your password:\n{reset_url}\n\nIf you didn’t request this, ignore this email."

        try:
            safe_send_mail(msg.subject, msg.recipients, msg.body)
            flash("Password reset email sent! Check your inbox.", "info")
        except Exception as e:
            print("Email send error:", e)
            flash("Failed to send email. Try again later.", "error")

        return redirect(url_for('auth.login_customer'))

    return render_template('forgot_password.html')

# ================= RESET PASSWORD =================
@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = get_serializer().loads(token, salt="password-reset", max_age=3600)  # 1 hour expiry
    except SignatureExpired:
        return "Reset link expired", 400
    except BadSignature:
        return "Invalid reset link", 400

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not password or not confirm_password:
            flash("Please fill all fields", "error")
            return redirect(url_for('auth.reset_password', token=token))
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return redirect(url_for('auth.reset_password', token=token))

        users = db.collection('customers').where('email', '==', email).get()
        if not users:
            return "User not found", 404

        hashed_password = generate_password_hash(password)
        users[0].reference.update({"password": hashed_password})
        flash("Password updated! You can now login.", "success")
        return redirect(url_for('auth.login_customer'))

    return render_template('reset_password.html', token=token)
