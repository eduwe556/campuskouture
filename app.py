import os
import logging
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

import cloudinary
import cloudinary.uploader

# Set up logging to show full errors
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Database URL handling (Neon provides postgresql:// with extra params)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# Remove channel_binding parameter and keep only sslmode
if database_url.startswith('postgresql://'):
    parsed = urlparse(database_url)
    query_params = {}
    if parsed.query:
        for param in parsed.query.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                if key == 'sslmode':
                    query_params[key] = value
    new_query = '&'.join(f'{k}={v}' for k, v in query_params.items())
    database_url = urlunparse(parsed._replace(query=new_query))

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'campus123')

db = SQLAlchemy(app)

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Models
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=True)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)   # stores Cloudinary secure URL
    vendor_name = db.Column(db.String(100), nullable=False)
    vendor_whatsapp = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    orders = db.relationship('Order', backref='product', lazy=True)

    def __repr__(self):
        return f"Product('{self.name}', '{self.price}')"

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_address = db.Column(db.String(200), nullable=False)
    size = db.Column(db.String(20), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f"Order('{self.customer_name}', '{self.status}')"

# Create tables (runs at startup)
with app.app_context():
    db.create_all()

# Helper
def is_admin_logged_in():
    return session.get('admin_logged_in', False)

# ---------- PUBLIC ROUTES ----------
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

    customer_name = request.form.get('customer_name')
    customer_phone = request.form.get('customer_phone')
    customer_address = request.form.get('customer_address')
    size = request.form.get('size') or None
    quantity = request.form.get('quantity') or 1

    if not customer_name or not customer_phone or not customer_address:
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('product_detail', product_id=product.id))

    try:
        quantity_int = int(quantity)
        if quantity_int < 1:
            quantity_int = 1
    except ValueError:
        quantity_int = 1

    order = Order(
        product_id=product.id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_address=customer_address,
        size=size,
        quantity=quantity_int
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

# ---------- ADMIN ROUTES ----------
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if is_admin_logged_in():
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        password = request.form.get('password')
        if password == app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
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

    if 'image' not in request.files:
        flash('No image uploaded.', 'error')
        return redirect(url_for('admin_dashboard'))

    image_file = request.files['image']
    if image_file.filename == '':
        flash('No image selected.', 'error')
        return redirect(url_for('admin_dashboard'))

    # Upload image to Cloudinary
    try:
        upload_result = cloudinary.uploader.upload(image_file)
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
        name=name,
        description=description,
        price=price_float,
        original_price=original_price_float,
        category=category,
        image_url=image_url,
        vendor_name=vendor_name,
        vendor_whatsapp=vendor_whatsapp
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
    else:
        flash('Invalid status.', 'error')

    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
