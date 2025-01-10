from datetime import datetime
from functools import wraps
from io import BytesIO

import pandas as pd
from flask import Blueprint, session, flash
from flask import render_template, request, redirect, url_for
from flask import send_file
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

from backend.app import login_manager  # Import the login_manager
from backend.models import User, db  # Import models and db from the correct location

main = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("Session:", session)  # Debugging line
        if 'user_id' not in session:
            flash('You must be logged in to access this page.', 'error')
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_role' not in session or session['user_role'] != 'manager':
            flash('You must be a manager to access this page.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)  # Ensure this returns the user object correctly

# Routes
@main.route('/')
def index():
    return render_template('base.html')



@main.route('/signup', methods=['GET', 'POST'])
def signup():
    # Check if admin accounts are limited to two
    admin_count = User.query.filter_by(role='admin').count()
    if admin_count >= 2:
        flash('Admin registration limit reached. Contact an existing admin.', 'error')
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']

        # Check if the email is already registered
        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'error')
            return redirect(url_for('main.signup'))

        # Create a new user object (admin or user based on your logic)
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password, role='admin', phone=phone)

        # Add the new user to the session and commit to the database
        db.session.add(new_user)
        db.session.commit()

        flash('Admin registration successful! Please log in.', 'success')
        return redirect(url_for('main.login'))

    return render_template('signup.html')



@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Find user by email
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            # Check if the user is an admin
            if user.role == 'admin':
                # Successful login for admin
                session['user_id'] = str(user.id)
                session['username'] = user.username
                session['user_role'] = user.role
                # Set is_active to True when logged in
                user.is_active = True
                db.session.commit()

                flash('Login successful!', 'success')
                return redirect(url_for('main.dashboard'))

            # Check role-based redirection
            elif user.role == 'bartender':
                session['user_id'] = str(user.id)
                session['username'] = user.username
                session['user_role'] = user.role
                user.is_active = True
                db.session.commit()

                flash('Login successful!', 'success')
                return redirect(url_for('main.bartender_dashboard'))  # Redirect to bartender dashboard

            elif user.role == 'event_planner':
                session['user_id'] = str(user.id)
                session['username'] = user.username
                session['user_role'] = user.role
                user.is_active = True
                db.session.commit()

                flash('Login successful!', 'success')
                return redirect(url_for('main.event_planner_dashboard'))  # Redirect to event planner dashboard

            elif user.role == 'restaurant_tender':
                session['user_id'] = str(user.id)
                session['username'] = user.username
                session['user_role'] = user.role
                user.is_active = True
                db.session.commit()

                flash('Login successful!', 'success')
                return redirect(url_for('main.restaurant_tender_dashboard'))  # Redirect to restaurant tender dashboard

            else:
                flash('Invalid role assigned.', 'error')
                return redirect(url_for('main.login'))

        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@main.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session.get('username'))

# Function to generate unique ID
def generate_unique_id():
    last_user = db.session.query(User).order_by(User.id.desc()).first()
    if last_user:
        return str(int(last_user.id) + 1)  # Increment last user ID
    else:
        return '001'  # Return '001' if no users are present

@main.route('/add_user', methods=['POST'])
@login_required
def add_user():
    if session.get('user_role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))

    # Extract form data
    full_name = request.form['full_name']
    email = request.form['email']
    password = request.form['password']
    id_number = request.form['id_number']
    phone = request.form['phone']
    role = request.form['role']

    # Check if email is already registered
    if User.query.filter_by(email=email).first():
        flash('Email is already registered.', 'error')
        return redirect(url_for('main.add_user_page'))

    # Generate a unique user ID
    new_user_id = generate_unique_id()

    # Hash the password
    hashed_password = generate_password_hash(password)

    # Create the new user with the unique ID
    new_user = User(
        id=new_user_id,  # Use the generated unique ID
        username=full_name,
        email=email,
        password=hashed_password,
        role=role,
        phone=phone
    )

    # Add and commit the new user to the database
    db.session.add(new_user)
    db.session.commit()

    flash('User added successfully!', 'success')
    return redirect(url_for('main.dashboard'))



@main.route('/export_users')  # Use the blueprint 'main' instead of 'app'
@login_required
def export_users():
    if session.get('user_role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))

    # Fetch all users
    users = User.query.all()

    # Prepare data for Excel
    user_data = []
    for user in users:
        user_data.append({
            'Full Name': user.username,
            'Email': user.email,
            'Role': user.role,
            'Phone': user.phone,
            'ID Number': user.id_number,
            'Status': 'Active' if user.is_active else 'Not Active'
        })

    # Create a DataFrame
    df = pd.DataFrame(user_data)

    # Convert to Excel in-memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Users')

    output.seek(0)

    # Send file as download
    return send_file(output, as_attachment=True, download_name="users_list.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@main.route('/add_user_page')
@login_required
def add_user_page():
    if session.get('user_role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))
    return render_template('add_user.html')

@main.route('/delete_user_page')
@login_required
def delete_user_page():
    if session.get('user_role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))
    users = User.query.all()  # Fetch all users
    return render_template('delete_user.html', users=users)

@main.route('/delete_user/<string:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == session.get('user_id'):
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('main.view_users'))

    db.session.delete(user)
    db.session.commit()

    flash('User deleted successfully!', 'success')
    return redirect(url_for('main.view_users'))

@main.route('/view_users')
@login_required
def view_users():
    if session.get('user_role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))
    users = User.query.all()
    return render_template('view_users.html', users=users)

@main.route('/edit_user/<uuid:user_id>', methods=['GET', 'POST'])  # UUID parameter in the route
@login_required
def edit_user(user_id):
    # Ensure user_id is a UUID before querying
    user_id_str = str(user_id)  # Convert UUID to string for SQLite compatibility
    user = User.query.get_or_404(user_id_str)  # Query by the string representation of the UUID

    if request.method == 'POST':
        user.full_name = request.form['full_name']
        user.email = request.form['email']
        user.id_number = request.form['id_number']
        user.phone = request.form['phone']
        user.role = request.form['role']

        # Optional: Handle password update
        password = request.form.get('password')
        if password:
            user.set_password(password)  # Assuming a method to hash the password

        db.session.commit()  # Save changes to the database
        return redirect(url_for('main.manage_users'))  # Redirect to the manage users page

    return render_template('edit_user.html', user=user)



@main.route('/update_user/<int:user_id>', methods=['POST'])
def update_user(user_id):
    user = User.query.get_or_404(user_id)

    # Process the form data
    if request.method == 'POST':
        user.full_name = request.form['full_name']
        user.email = request.form['email']
        user.id_number = request.form['id_number']
        user.phone = request.form['phone']
        user.role = request.form['role']

        password = request.form.get('password')
        if password:
            user.set_password(password)  # Assuming a method to hash the password

        db.session.commit()  # Save changes to the database

        return redirect(url_for('main.manage_users'))  # Redirect to the manage users page

    return render_template('edit_user.html', user=user)


@main.route('/assign_roles')
@login_required
def assign_roles():
    if session.get('user_role') != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))
    users = User.query.all()
    return render_template('assign_roles.html', users=users)



@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user.username = request.form['name']
        user.phone = request.form['phone']
        # email field will not be updated, as it is read-only
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.profile'))

    return render_template('profile.html', user=user)


@main.route('/menu/restaurant', methods=['GET'])
@login_required
def restaurant_menu():
    # Use SQLAlchemy's text() function to handle raw SQL queries
    result = db.session.execute(text("SELECT * FROM menu_items WHERE type='restaurant'")).fetchall()
    is_open = 9 <= datetime.now().hour <= 21
    return render_template('restaurant_menu.html', menu=result, is_open=is_open)

@main.route('/menu/bar', methods=['GET'])
@login_required
def bar_menu():
    # Logic for bar menu
    return render_template('bar_menu.html')

@main.route('/menu/order', methods=['POST'])
@login_required
def place_order():
    order_details = {
        'user_id': session['user_id'],
        'food_item': request.form['food_item'],
        'pickup_time': request.form['pickup_time'],
        'status': 'Pending',
        'order_time': datetime.now()
    }

    pickup_hour = int(order_details['pickup_time'].split(':')[0])
    if pickup_hour < 9 or pickup_hour > 21:
        flash('Pickup time must be between 9:00 AM and 9:00 PM.', 'error')
        return redirect(url_for('main.restaurant_menu'))

    db.session.execute(
        "INSERT INTO orders (user_id, food_item, pickup_time, status, order_time) "
        "VALUES (:user_id, :food_item, :pickup_time, :status, :order_time)",
        order_details
    )
    db.session.commit()

    flash('Order placed successfully!', 'success')
    return redirect(url_for('main.dashboard'))

@main.route('/admin/dashboard', methods=['GET'])
@manager_required
def admin_dashboard():
    # Count orders for the admin dashboard
    total_orders = db.session.execute("SELECT COUNT(*) FROM orders").scalar()
    pending_orders = db.session.execute("SELECT COUNT(*) FROM orders WHERE status='Pending'").scalar()
    completed_orders = db.session.execute("SELECT COUNT(*) FROM orders WHERE status='Completed'").scalar()

    return render_template(
        'admin_dashboard.html',
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
    )

@main.route('/rooms', methods=['GET'])
@login_required
def room_list():
    # Correct the raw SQL query by wrapping it with text()
    rooms = db.session.execute(text("SELECT * FROM rooms")).fetchall()
    return render_template('rooms.html', rooms=rooms)

@main.route('/rooms/book', methods=['POST'])
@login_required
def book_room():
    room_id = request.form['room_id']
    user_details = {
        'name': request.form['name'],
        'phone': request.form['phone'],
        'arrival_date': request.form['arrival_date'],
        'hours': request.form['hours'],
    }

    room = db.session.execute(
        "SELECT * FROM rooms WHERE id=:room_id AND status='available'", {'room_id': room_id}
    ).fetchone()

    if not room:
        flash('Room is not available.', 'error')
        return redirect(url_for('main.room_list'))

    db.session.execute(
        "UPDATE rooms SET status='booked', booked_by=:user_details WHERE id=:room_id",
        {'user_details': user_details, 'room_id': room_id}
    )
    db.session.commit()

    flash('Room booked successfully!', 'success')
    send_booking_notification(user_details, room_id)
    return redirect(url_for('main.room_list'))

# Notification functions
def send_booking_notification(user_details, room_id):
    message = (
        f"Hello {user_details['name']},\n\n"
        f"Your room (ID: {room_id}) is booked.\n"
        f"Arrival Date: {user_details['arrival_date']}\n"
        f"Duration: {user_details['hours']} hours\n\n"
        "Thank you for choosing our service!"
    )
    print(f"Notification sent: {message}")



@main.route('/bartender_dashboard')
def bartender_dashboard():
    # Your logic to fetch the opening_balance
    opening_balance = get_opening_balance()  # Example function to get the balance
    return render_template('bartender_dashboard.html', opening_balance=opening_balance)

def get_opening_balance():
    # Example static value, replace with your actual logic
    return {'amount': 1000}



@main.route('/bar_dashboard')
@login_required
def bar_dashboard():
    if session.get('user_role') != 'bartender':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))

    # Example: Retrieve bar events and other necessary information
    events = BarEvent.query.all()  # Assuming you have a BarEvent model
    opening_balance = BarStock.query.first()  # Retrieve opening balance
    return render_template('bartender_dashboard.html', events=events, opening_balance=opening_balance)


@main.route('/event_planner_dashboard')
@login_required
def event_planner_dashboard():
    if session.get('user_role') != 'event_planner':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))

    return render_template('event_planner_dashboard.html')  # Template for event planner


@main.route('/restaurant_dashboard')
@login_required
def restaurant_dashboard():
    if session.get('user_role') != 'restaurant_tender':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))

    # Example: Retrieve food items and their availability status
    food_items = Food.query.all()  # Assuming you have a Food model for this

    return render_template('restaurant_tender_dashboard.html', food_items=food_items)


@main.route('/order_food/<int:food_id>', methods=['GET', 'POST'])
@login_required
def order_food(food_id):
    food = Food.query.get(food_id)

    if request.method == 'POST':
        customer_name = request.form['name']
        phone_number = request.form['phone']
        collection_time = request.form['collection_time']

        # Validate collection time is between 9:30 and 21:30
        if not (9 <= int(collection_time.split(":")[0]) <= 21):
            flash('Invalid collection time. Must be between 9:30 and 21:30.', 'error')
            return redirect(url_for('main.order_food', food_id=food.id))

        # Process payment (this could integrate with a payment gateway)
        payment_method = request.form['payment_method']

        # Send confirmation message to customer and notify the kitchen
        # You can integrate email or SMS here

        flash(f"Thank you! Your order for {food.name} will be ready at {collection_time}.", 'success')
        return redirect(url_for('main.restaurant_dashboard'))

    return render_template('order_food.html', food=food)


@main.route('/room_dashboard')
@login_required
def room_dashboard():
    if session.get('user_role') != 'event_planner':
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))

    rooms = Room.query.filter_by(is_available=True).all()  # Fetch available rooms
    return render_template('event_planner_dashboard.html', rooms=rooms)


# Route for booking a specific room with a given room_id
@main.route('/book_room/<int:room_id>', methods=['GET', 'POST'], endpoint='book_specific_room')
@login_required
def book_room(room_id):
    room = Room.query.get(room_id)

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        arrival_date = request.form['arrival_date']
        duration = request.form['duration']

        # Process payment (integrate with a payment gateway)
        payment_method = request.form['payment_method']

        # Send confirmation message and notify the manager
        flash('Room booking successful!', 'success')
        return redirect(url_for('main.room_dashboard'))

    return render_template('book_room.html', room=room)

# Route for the general room list (no room_id) - renamed function
@main.route('/book_room_list', methods=['POST'], endpoint='book_room_list')
@login_required
def book_room_list():
    room_id = request.form['room_id']
    # Your logic for booking a room from the list

    return redirect(url_for('main.room_list'))


@main.route('/logout', methods=['POST'])
@login_required
def logout():
    # Check if the user is logged in
    if not session.get('user_id'):
        flash('No user is logged in', 'error')
        return redirect(url_for('main.login'))

    # Retrieve the user from the database
    user = User.query.get(session['user_id'])

    if user is None:
        flash('User not found', 'error')
        return redirect(url_for('main.login'))

    # Set the user's 'is_active' to False on logout
    user.is_active = False
    db.session.commit()

    # Clear session variables
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('user_role', None)

    # Flash a success message
    flash('You have been logged out successfully!', 'success')

    # Redirect to the login page
    return redirect(url_for('main.login'))
