import os
import logging
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

import cloudinary
import cloudinary.uploader

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True

# ---------------- CONFIG ----------------
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

database_url = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
if database_url.startswith('postgresql://'):
    parsed = urlparse(database_url)
    q = {}
    if parsed.query:
        for p in parsed.query.split('&'):
            if '=' in p:
                k, v = p.split('=', 1)
                if k == 'sslmode':
                    q[k] = v
    database_url = urlunparse(parsed._replace(query='&'.join(f'{k}={v}' for k, v in q.items())))

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'campus123')
app.config['VENDOR_FEE'] = 2000

db = SQLAlchemy(app)

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------------- MODELS ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='buyer')
    is_subscribed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    orders = db.relationship('Order', backref='user', lazy=True)
    products = db.relationship('Product', backref='vendor_account', lazy=True)

    def __repr__(self):
        return f"User('{self.email}', '{self.role}')"

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000), nullable=True)
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=True)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    vendor_name = db.Column(db.String(100), nullable=False)
    vendor_whatsapp = db.Column(db.String(20), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    orders = db.relationship('Order', backref='product', lazy=True)

    def __repr__(self):
        return f"Product('{self.name}', '{self.price}')"

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_address = db.Column(db.String(200), nullable=False)
    size = db.Column(db.String(20), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    promo_code = db.Column(db.String(50), nullable=True)
    discount_amount = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    messages = db.relationship('Message', backref='order', lazy=True, order_by='Message.created_at')

    def __repr__(self):
        return f"Order('{self.customer_name}', '{self.status}')"

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    sender = db.relationship('User', foreign_keys=[sender_id])

    def __repr__(self):
        return f"Message('{self.sender_id}')"

with app.app_context():
    db.create_all()

# ---------------- HELPERS ----------------

def is_admin_logged_in():
    return session.get('admin_logged_in', False)

def current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None

@app.context_processor
def inject_user():
    return dict(current_user=current_user())

def validate_promo_code(code):
    if not code:
        return 0, None
    code = code.strip().upper()
    if code == 'CAMPUS10':
        return 0.10, code
    if code == 'FREEDELIVERY':
        return 1000.0, code
    return 0, None

def vendor_can_manage(vendor, product):
    return vendor and vendor.role == 'vendor' and product.vendor_id == vendor.id

def can_view_order(order, user):
    if not user:
        return False
    if user.id == order.user_id:
        return True
    if order.product.vendor_id == user.id:
        return True
    return False

# ---------------- PUBLIC ROUTES ----------------

@app.route('/')
def home():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('index.html', products=products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

@app.route('/order/<int:product_id>', methods=['POST'])
def place_order(product_id):
    product = Product.query.get_or_404(product_id)
    user = current_user()

    customer_name = request.form.get('customer_name')
    customer_phone = request.form.get('customer_phone')
    customer_address = request.form.get('customer_address')
    size = request.form.get('size') or None
    quantity = request.form.get('quantity') or 1
    promo_code_input = request.form.get('promo_code', '').strip()

    if not customer_name or not customer_phone or not customer_address:
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('product_detail', product_id=product.id))

    try:
        qty = int(quantity)
        if qty < 1:
            qty = 1
    except ValueError:
        qty = 1

    discount_value, code_used = validate_promo_code(promo_code_input)
    total = product.price * qty
    if discount_value and code_used == 'CAMPUS10':
        discount_amount = total * 0.10
    elif discount_value and code_used == 'FREEDELIVERY':
        discount_amount = 1000.0
    else:
        discount_amount = 0.0
        code_used = None

    order = Order(
        product_id=product.id,
        user_id=user.id if user else None,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_address=customer_address,
        size=size,
        quantity=qty,
        promo_code=code_used,
        discount_amount=discount_amount
    )
    db.session.add(order)
    db.session.commit()

    flash('Order placed successfully! We will contact you shortly.', 'success')
    return redirect(url_for('order_success', order_id=order.id))

@app.route('/order-success/<int:order_id>')
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_success.html', order=order)

@app.route('/about')
def about():
    return render_template('about.html')

# ---------------- AUTH ----------------

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user():
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        role = request.form.get('role', 'buyer')

        if role not in ('buyer', 'vendor'):
            role = 'buyer'

        if not name or not email or not password:
            flash('Please fill all fields.', 'error')
            return redirect(url_for('signup'))
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('signup'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return redirect(url_for('login'))

        user = User(name=name, email=email, role=role,
                    password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        flash(f'Welcome to CampusKouture, {user.name}!', 'success')

        if role == 'vendor':
            return redirect(url_for('vendor_dashboard'))
        return redirect(url_for('home'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user():
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash(f'Welcome back, {user.name}!', 'success')
            if user.role == 'vendor':
                return redirect(url_for('vendor_dashboard'))
            return redirect(url_for('home'))
        flash('Invalid email or password.', 'error')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# ---------------- BUYER ----------------

@app.route('/my-orders')
def my_orders():
    user = current_user()
    if not user:
        flash('Please log in to view your orders.', 'error')
        return redirect(url_for('login'))
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)

# ---------------- VENDOR ----------------

@app.route('/vendor/dashboard')
def vendor_dashboard():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if user.role != 'vendor':
        flash('Only vendors can access the seller dashboard.', 'error')
        return redirect(url_for('home'))

    products = Product.query.filter_by(vendor_id=user.id).order_by(Product.created_at.desc()).all()
    product_ids = [p.id for p in products]
    orders = Order.query.filter(Order.product_id.in_(product_ids)).order_by(Order.created_at.desc()).all() if product_ids else []
    return render_template('vendor/dashboard.html', user=user, products=products, orders=orders,
                           fee=app.config['VENDOR_FEE'])

@app.route('/vendor/subscribe', methods=['POST'])
def vendor_subscribe():
    user = current_user()
    if not user or user.role != 'vendor':
        return redirect(url_for('login'))
    # DEMO: instant flip. Replace with Paystack later.
    user.is_subscribed = True
    db.session.commit()
    flash('Subscription activated! You can now add products.', 'success')
    return redirect(url_for('vendor_dashboard'))

@app.route('/vendor/add_product', methods=['POST'])
def vendor_add_product():
    user = current_user()
    if not user or user.role != 'vendor':
        return redirect(url_for('login'))
    if not user.is_subscribed:
        flash('Please subscribe to start listing products.', 'error')
        return redirect(url_for('vendor_dashboard'))

    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    original_price = request.form.get('original_price') or None
    category = request.form.get('category')
    vendor_whatsapp = request.form.get('vendor_whatsapp')

    if not name or not price or not category or not vendor_whatsapp:
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('vendor_dashboard'))

    if 'image' not in request.files or request.files['image'].filename == '':
        flash('Please upload a product image.', 'error')
        return redirect(url_for('vendor_dashboard'))

    try:
        upload_result = cloudinary.uploader.upload(request.files['image'])
        image_url = upload_result['secure_url']
    except Exception as e:
        flash(f'Image upload failed: {str(e)}', 'error')
        return redirect(url_for('vendor_dashboard'))

    try:
        price_float = float(price)
        original_price_float = float(original_price) if original_price else None
    except ValueError:
        flash('Price must be a number.', 'error')
        return redirect(url_for('vendor_dashboard'))

    product = Product(
        name=name, description=description, price=price_float,
        original_price=original_price_float, category=category,
        image_url=image_url, vendor_name=user.name,
        vendor_whatsapp=vendor_whatsapp, vendor_id=user.id
    )
    db.session.add(product)
    db.session.commit()
    flash('Product added and live on the site!', 'success')
    return redirect(url_for('vendor_dashboard'))

@app.route('/vendor/delete_product/<int:product_id>', methods=['POST'])
def vendor_delete_product(product_id):
    user = current_user()
    product = Product.query.get_or_404(product_id)
    if not vendor_can_manage(user, product):
        flash('Not allowed.', 'error')
        return redirect(url_for('vendor_dashboard'))
    Order.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted.', 'info')
    return redirect(url_for('vendor_dashboard'))

@app.route('/vendor/update_order_status/<int:order_id>', methods=['POST'])
def vendor_update_order_status(order_id):
    user = current_user()
    order = Order.query.get_or_404(order_id)
    if not user or order.product.vendor_id != user.id:
        flash('Not allowed.', 'error')
        return redirect(url_for('vendor_dashboard'))
    new_status = request.form.get('status')
    if new_status in ['Pending', 'Paid', 'Completed']:
        order.status = new_status
        db.session.commit()
        flash(f'Order #{order.id} updated to {new_status}.', 'success')
    return redirect(url_for('vendor_dashboard'))

# ---------------- ORDER MESSAGES ----------------

@app.route('/order/<int:order_id>/messages', methods=['GET', 'POST'])
def order_messages(order_id):
    user = current_user()
    order = Order.query.get_or_404(order_id)
    if not can_view_order(order, user):
        flash('You do not have access to this order.', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if body:
            msg = Message(order_id=order.id, sender_id=user.id, body=body)
            db.session.add(msg)
            db.session.commit()
        return redirect(url_for('order_messages', order_id=order.id))

    return render_template('order_messages.html', order=order)

# ---------------- ADMIN ----------------

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if is_admin_logged_in():
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        if request.form.get('password') == app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Incorrect password. Try again.', 'error')
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    products = Product.query.order_by(Product.created_at.desc()).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/dashboard.html', products=products, orders=orders)

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))

    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    original_price = request.form.get('original_price') or None
    category = request.form.get('category')
    vendor_name = request.form.get('vendor_name')
    vendor_whatsapp = request.form.get('vendor_whatsapp')

    if not name or not price or not category or not vendor_name or not vendor_whatsapp:
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('admin_dashboard'))
    if 'image' not in request.files or request.files['image'].filename == '':
        flash('Please upload an image.', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        upload_result = cloudinary.uploader.upload(request.files['image'])
        image_url = upload_result['secure_url']
    except Exception as e:
        flash(f'Image upload failed: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        price_float = float(price)
        original_price_float = float(original_price) if original_price else None
    except ValueError:
        flash('Price must be a number.', 'error')
        return redirect(url_for('admin_dashboard'))

    product = Product(
        name=name, description=description, price=price_float,
        original_price=original_price_float, category=category,
        image_url=image_url, vendor_name=vendor_name,
        vendor_whatsapp=vendor_whatsapp, vendor_id=None
    )
    db.session.add(product)
    db.session.commit()
    flash('Product added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    product = Product.query.get_or_404(product_id)
    Order.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    if not is_admin_logged_in():
        return redirect(url_for('admin_login'))
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    if new_status in ['Pending', 'Paid', 'Completed']:
        order.status = new_status
        db.session.commit()
        flash(f'Order #{order.id} status updated to {new_status}.', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)