import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, User, Service, Staff, Appointment

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///salon.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ---------- Template Helpers (inline templates) ----------
BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Salon App</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }
        nav { background: #4a148c; padding: 15px; color: white; }
        nav a { color: white; margin-right: 15px; text-decoration: none; }
        .container { max-width: 900px; margin: 20px auto; background: white; padding: 20px; border-radius: 8px; }
        .flash { padding: 10px; margin: 10px 0; border-radius: 4px; background: #e3f2fd; }
        .flash.error { background: #ffcdd2; }
        .flash.success { background: #c8e6c9; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
        th { background: #f3e5f5; }
        input, select, textarea { padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; }
        button, .btn { background: #4a148c; color: white; padding: 10px 15px; border: none; cursor: pointer;
                       text-decoration: none; border-radius: 4px; display: inline-block; }
        button:hover, .btn:hover { background: #6a1b9a; }
        .btn-danger { background: #c62828; }
        .btn-danger:hover { background: #e53935; }
    </style>
</head>
<body>
<nav>
    <a href="/">Home</a>
    {% if current_user.is_authenticated %}
        <a href="/appointments">My Appointments</a>
        <a href="/book">Book Appointment</a>
        {% if current_user.role == 'admin' %}
            <a href="/admin">Admin</a>
        {% endif %}
        <span style="float:right;">
            Hi, {{ current_user.username }} | <a href="/logout">Logout</a>
        </span>
    {% else %}
        <span style="float:right;">
            <a href="/login">Login</a> | <a href="/register">Register</a>
        </span>
    {% endif %}
</nav>
<div class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, msg in messages %}
        <div class="flash {{ category }}">{{ msg }}</div>
      {% endfor %}
    {% endwith %}
    {% block content %}{% endblock %}
</div>
</body>
</html>
"""


def render_page(body, **kwargs):
    """Very small inline-template renderer (avoids needing a templates folder)."""
    from jinja2 import Template
    template = Template(BASE_TEMPLATE.replace("{% block content %}{% endblock %}", body))
    return template.render(**kwargs)


# ---------- Routes ----------
@app.route('/')
def index():
    services = Service.query.all()
    rows = ''.join(
        f"<tr><td>{s.name}</td><td>{s.description or ''}</td>"
        f"<td>${s.price:.2f}</td><td>{s.duration_minutes} min</td></tr>"
        for s in services
    ) or "<tr><td colspan='4'>No services yet.</td></tr>"

    body = f"""
    <h1>Welcome to Our Salon</h1>
    <p>Book your appointment online in seconds.</p>
    <h2>Our Services</h2>
    <table>
        <tr><th>Service</th><th>Description</th><th>Price</th><th>Duration</th></tr>
        {rows}
    </table>
    <br>
    <a class="btn" href="/book">Book Now</a>
    """
    return render_page(body, current_user=current_user)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('All fields required.', 'error')
            return redirect(url_for('register'))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or email already registered.', 'error')
            return redirect(url_for('register'))

        user = User(username=username, email=email, role='customer')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))

    body = """
    <h1>Register</h1>
    <form method="POST">
        <label>Username</label><input name="username" required>
        <label>Email</label><input name="email" type="email" required>
        <label>Password</label><input name="password" type="password" required>
        <button type="submit">Register</button>
    </form>
    """
    return render_page(body, current_user=current_user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials.', 'error')

    body = """
    <h1>Login</h1>
    <form method="POST">
        <label>Username</label><input name="username" required>
        <label>Password</label><input name="password" type="password" required>
        <button type="submit">Login</button>
    </form>
    """
    return render_page(body, current_user=current_user)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    services = Service.query.all()
    staff_list = Staff.query.filter_by(available=True).all()

    if request.method == 'POST':
        service_id = request.form.get('service_id')
        staff_id = request.form.get('staff_id')
        date_str = request.form.get('appointment_date')
        notes = request.form.get('notes', '')

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            flash('Invalid date/time.', 'error')
            return redirect(url_for('book'))

        appt = Appointment(
            user_id=current_user.id,
            service_id=service_id,
            staff_id=staff_id,
            appointment_date=appt_date,
            notes=notes,
            status='pending'
        )
        db.session.add(appt)
        db.session.commit()
        flash('Appointment booked!', 'success')
        return redirect(url_for('appointments'))

    service_opts = ''.join(
        f'<option value="{s.id}">{s.name} - ${s.price:.2f} ({s.duration_minutes} min)</option>'
        for s in services
    )
    staff_opts = ''.join(
        f'<option value="{s.id}">{s.name} ({s.specialty or "general"})</option>'
        for s in staff_list
    )

    body = f"""
    <h1>Book an Appointment</h1>
    <form method="POST">
        <label>Service</label>
        <select name="service_id" required>{service_opts}</select>
        <label>Staff</label>
        <select name="staff_id" required>{staff_opts}</select>
        <label>Date &amp; Time</label>
        <input type="datetime-local" name="appointment_date" required>
        <label>Notes</label>
        <textarea name="notes" rows="3"></textarea>
        <button type="submit">Book</button>
    </form>
    """
    return render_page(body, current_user=current_user)


@app.route('/appointments')
@login_required
def appointments():
    if current_user.role == 'admin':
        appts = Appointment.query.order_by(Appointment.appointment_date).all()
    else:
        appts = Appointment.query.filter_by(user_id=current_user.id) \
            .order_by(Appointment.appointment_date).all()

    rows = ''
    for a in appts:
        cancel = ''
        if a.status in ('pending', 'confirmed'):
            cancel = f'<a class="btn btn-danger" href="/appointments/{a.id}/cancel">Cancel</a>'
        rows += (
            f"<tr><td>{a.id}</td>"
            f"<td>{a.service.name if a.service else '-'}</td>"
            f"<td>{a.staff.name if a.staff else '-'}</td>"
            f"<td>{a.appointment_date.strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{a.status}</td><td>{cancel}</td></tr>"
        )
    if not rows:
        rows = "<tr><td colspan='6'>No appointments yet.</td></tr>"

    body = f"""
    <h1>Appointments</h1>
    <table>
        <tr><th>ID</th><th>Service</th><th>Staff</th><th>Date</th><th>Status</th><th>Action</th></tr>
        {rows}
    </table>
    """
    return render_page(body, current_user=current_user)


@app.route('/appointments/<int:appt_id>/cancel', methods=['GET', 'POST'])
@login_required
def cancel_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.user_id != current_user.id and current_user.role != 'admin':
        abort(403)
    appt.status = 'cancelled'
    db.session.commit()
    flash('Appointment cancelled.', 'success')
    return redirect(url_for('appointments'))


# ---------- Admin ----------
@app.route('/admin')
@login_required
@admin_required
def admin():
    body = """
    <h1>Admin Dashboard</h1>
    <ul>
        <li><a href="/admin/services">Manage Services</a></li>
        <li><a href="/admin/staff">Manage Staff</a></li>
        <li><a href="/admin/appointments">All Appointments</a></li>
    </ul>
    """
    return render_page(body, current_user=current_user)


@app.route('/admin/services', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_services():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        price = float(request.form.get('price', 0))
        duration = int(request.form.get('duration', 30))
        db.session.add(Service(name=name, description=description,
                               price=price, duration_minutes=duration))
        db.session.commit()
        flash('Service added.', 'success')
        return redirect(url_for('admin_services'))

    services = Service.query.all()
    rows = ''.join(
        f"<tr><td>{s.id}</td><td>{s.name}</td><td>${s.price:.2f}</td>"
        f"<td>{s.duration_minutes} min</td>"
        f"<td><a class='btn btn-danger' href='/admin/services/{s.id}/delete'>Delete</a></td></tr>"
        for s in services
    ) or "<tr><td colspan='5'>No services.</td></tr>"

    body = f"""
    <h1>Manage Services</h1>
    <form method="POST">
        <label>Name</label><input name="name" required>
        <label>Description</label><input name="description">
        <label>Price</label><input name="price" type="number" step="0.01" required>
        <label>Duration (minutes)</label><input name="duration" type="number" value="30">
        <button type="submit">Add Service</button>
    </form>
    <table>
        <tr><th>ID</th><th>Name</th><th>Price</th><th>Duration</th><th>Action</th></tr>
        {rows}
    </table>
    """
    return render_page(body, current_user=current_user)


@app.route('/admin/services/<int:service_id>/delete', methods=['POST', 'GET'])
@login_required
@admin_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash('Service deleted.', 'success')
    return redirect(url_for('admin_services'))


@app.route('/admin/staff', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_staff():
    if request.method == 'POST':
        name = request.form.get('name')
        specialty = request.form.get('specialty', '')
        phone = request.form.get('phone', '')
        db.session.add(Staff(name=name, specialty=specialty, phone=phone))
        db.session.commit()
        flash('Staff added.', 'success')
        return redirect(url_for('admin_staff'))

    staff_list = Staff.query.all()
    rows = ''.join(
        f"<tr><td>{s.id}</td><td>{s.name}</td><td>{s.specialty or ''}</td>"
        f"<td>{s.phone or ''}</td><td>{'Yes' if s.available else 'No'}</td></tr>"
        for s in staff_list
    ) or "<tr><td colspan='5'>No staff.</td></tr>"

    body = f"""
    <h1>Manage Staff</h1>
    <form method="POST">
        <label>Name</label><input name="name" required>
        <label>Specialty</label><input name="specialty">
        <label>Phone</label><input name="phone">
        <button type="submit">Add Staff</button>
    </form>
    <table>
        <tr><th>ID</th><th>Name</th><th>Specialty</th><th>Phone</th><th>Available</th></tr>
        {rows}
    </table>
    """
    return render_page(body, current_user=current_user)


@app.route('/admin/appointments')
@login_required
@admin_required
def admin_appointments():
    appts = Appointment.query.order_by(Appointment.appointment_date).all()
    rows = ''
    for a in appts:
        rows += (
            f"<tr><td>{a.id}</td><td>{a.user.username}</td>"
            f"<td>{a.service.name if a.service else '-'}</td>"
            f"<td>{a.staff.name if a.staff else '-'}</td>"
            f"<td>{a.appointment_date.strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{a.status}</td>"
            f"<td>"
            f"<a class='btn' href='/admin/appointments/{a.id}/status/confirmed'>Confirm</a> "
            f"<a class='btn' href='/admin/appointments/{a.id}/status/completed'>Complete</a> "
            f"<a class='btn btn-danger' href='/admin/appointments/{a.id}/status/cancelled'>Cancel</a>"
            f"</td></tr>"
        )
    if not rows:
        rows = "<tr><td colspan='7'>No appointments.</td></tr>"

    body = f"""
    <h1>All Appointments</h1>
    <table>
        <tr><th>ID</th><th>User</th><th>Service</th><th>Staff</th><th>Date</th><th>Status</th><th>Action</th></tr>
        {rows}
    </table>
    """
    return render_page(body, current_user=current_user)


@app.route('/admin/appointments/<int:appt_id>/status/<status>', methods=['GET', 'POST'])
@login_required
@admin_required
def update_appt_status(appt_id, status):
    if status not in ('pending', 'confirmed', 'completed', 'cancelled'):
        abort(400)
    appt = Appointment.query.get_or_404(appt_id)
    appt.status = status
    db.session.commit()
    flash(f'Appointment marked as {status}.', 'success')
    return redirect(url_for('admin_appointments'))


# ---------- CLI init ----------
@app.cli.command('init-db')
def init_db():
    """Initialize the database and create an admin user."""
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@salon.local', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
    if Service.query.count() == 0:
        db.session.add_all([
            Service(name='Haircut', description='Classic haircut', price=25.0, duration_minutes=30),
            Service(name='Hair Color', description='Full color treatment', price=75.0, duration_minutes=90),
            Service(name='Manicure', description='Basic manicure', price=20.0, duration_minutes=30),
        ])
    if Staff.query.count() == 0:
        db.session.add_all([
            Staff(name='Alice', specialty='Hair Stylist', phone='555-0101'),
            Staff(name='Bob', specialty='Barber', phone='555-0102'),
        ])
    db.session.commit()
    print('Database initialized. Admin login: admin / admin123')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
