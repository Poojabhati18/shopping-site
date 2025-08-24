# auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from firebase_config import db  # Your initialized Firestore
from datetime import datetime

auth = Blueprint('auth', __name__)

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

# ================= SIGNUP =================
@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        agree = request.form.get('agree')

        if not all([name, email, password, agree]):
            return render_template('signup.html', error="Please fill all fields and agree to terms")

        # Check if user already exists
        existing_users = db.collection('customers').where('email', '==', email).get()
        if existing_users:
            return render_template('signup.html', error="Email already registered. Please login.")

        # Hash password
        hashed_password = generate_password_hash(password)

        # Save to Firebase
        customer_ref = db.collection('customers').document()
        customer_ref.set({
            'name': name,
            'email': email,
            'password': hashed_password,
            'date_created': str(datetime.now())
        })

        # Redirect to login page after signup
        return redirect(url_for('auth.login_customer'))

    # GET request renders signup page
    return render_template('signup.html')

# ================= LOGIN =================
@auth.route('/loginC', methods=['GET', 'POST'])
def login_customer():
    if request.method == 'POST':
        email = request.form.get('email')
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

        if not check_password_hash(user_data['password'], password):
            return render_template('loginC.html', error="Invalid email or password")

        # Store in session
        session['customer'] = {
            'id': user_doc.id,
            'name': user_data['name'],
            'email': user_data['email']
        }

        return redirect(url_for('home'))

    return render_template('loginC.html')


# ================= LOGOUT =================
@auth.route('/logout_customer')
def logout_customer():
    session.pop('customer', None)
    return redirect('/')  # or wherever you want to redirect