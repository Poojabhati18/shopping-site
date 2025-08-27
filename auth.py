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

        # Save to Firebase
        customer_ref = db.collection('customers').document()
        customer_ref.set({
            'name': name,
            'email': email,
            'password': hashed_password,
            'date_created': str(datetime.now())
        })

        # Redirect to login page after signup
        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for('auth.login_customer'))

    # GET request renders signup page
    return render_template('signup.html')

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