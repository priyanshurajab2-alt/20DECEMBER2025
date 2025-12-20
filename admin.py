# admin.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
import sqlite3
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Persistent DB file path on Render
USER_DB_FILE = '/var/data/admin_users.db'

# Helper: Get DB connection to centralized user DB
def get_user_db_connection():
    conn = sqlite3.connect(USER_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Decorator to restrict access to admin users
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_type') != 'admin':
            flash('Admin access only. Please login as admin.', 'warning')
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated

# Admin login route
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_user_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            if user['user_type'] == 'admin':
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['user_type'] = user['user_type']
                session.permanent = True
                flash(f'Welcome Admin {user["username"]}!', 'success')
                return redirect(url_for('admin.admin_dashboard'))
            else:
                flash('Only admins may login here.', 'danger')
                return redirect(url_for('admin.admin_login'))
        else:
            flash('Invalid admin credentials.', 'danger')
            return redirect(url_for('admin.admin_login'))

    return render_template('admin_login.html')

# Admin dashboard route - protected
@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    # Example: You can show any admin overview or management page here
    return render_template('admin_dashboard.html')

# Admin logout route
@admin_bp.route('/logout')
@admin_required
def admin_logout():
    session.clear()
    flash('Admin logged out successfully.', 'info')
    return redirect(url_for('admin.admin_login'))

# Example admin-only route to manage users (add more as needed)
@admin_bp.route('/users')
@admin_required
def admin_users():
    conn = get_user_db_connection()
    users = conn.execute('SELECT id, username, email, user_type FROM users').fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

# Add your other admin routes here (e.g., content access setup, migration, etc.)

