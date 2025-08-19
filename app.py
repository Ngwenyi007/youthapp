import os
import re
import uuid
import json
import random
import string
import fcntl
import base64
import io
import smtplib
from datetime import datetime, timedelta, date
from functools import wraps
from threading import Thread
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Third-party Imports
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from flask import (
    Flask, render_template, send_from_directory, request,
    redirect, session, flash, jsonify, current_app,
    url_for
)
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired

# Load environment variables from a .env file.
# This is a common practice for managing configuration secrets.
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__)

# --- App Configuration ---
# Loads from environment variables for security.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
port = int(os.environ.get("PORT", 5000))

# --- Mail Configuration ---
# All mail credentials should be loaded from environment variables for production.
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your_email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your_password')

# --- Extension and Service Initialization ---
csrf = CSRFProtect(app)
socketio = SocketIO(app, cors_allowed_origins="*")
mail = Mail(app)  # Correctly initialize Mail with the app instance.

# --- File Paths and Directory Setup ---
USER_FILE = 'users.json'
POST_FILE = 'posts.json'
COMMENT_FILE = 'comments.json'
EVENT_FILE = 'events.json'
NOTIFICATION_FILE = 'notifications.json'
MESSAGE_FILE = 'messages.json'
PRAYER_FILE = 'prayers.json'
ATTENDANCE_FILE = 'attendance.json'

# Create upload directories and set upload folder path
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'events'), exist_ok=True)

# --- Application Data and Role Definitions ---
username = "code"
LEVEL_MAP = {
    'local': ('local_church', 'local_church'),
    'parish': ('parish', 'parish'),
    'denary': ('denary', 'denary'),
    'diocese': ('diocese', 'diocese'),
    'archdiocese': ('archdiocese', 'archdiocese')
}
role_definitions = {
    'Local': ['member', 'chairman', 'secretary', 'organising secretary', 'chaplain', 'matron', 'patron', 'treasurer'],
    'Parish': ['chaplain', 'chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer'],
    'Denary': ['chaplain', 'chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer'],
    'Diocese': ['chaplain', 'chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer'],
    'Archdiocese': ['chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer']
}

class LoginForm(FlaskForm):
    username = StringField('Member Code', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

def send_welcome_email(recipient, name, code):
    sender_email = "francismatu8@gmail.com"
    sender_password = "kyqdvvtqsvnaljpn"  # NOT your Gmail password, but an app password
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    subject = "Welcome to Youth App 🎉"
    body = f"""
    Hello {name},

    Welcome to our youth app! 🎊
    Your member code is: {code}.

    Please keep it safe — you’ll need it to log in.

    Regards,
    The Youth App Team
    """

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Send
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        user_posts=user_posts

def get_user_by_code(user_code):
    """Fetch user data from your database by user code"""
    try:
        with open('users.json', 'r') as f:  # Assuming JSON storage
            users = json.load(f)
            return next((u for u in users if u.get('code') == user_code), None)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def save_to_json(data, filename):
    with open(filename, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # Lock file
        try:
            existing = json.load(f)
            existing.append(data)
            f.seek(0)
            json.dump(existing, f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)  # Unlock

def fix_missing_post_ids():
    # Load posts
    if os.path.exists(POST_FILE):
        try:
            with open(POST_FILE, "r") as f:
                posts = json.load(f)
        except Exception:
            posts = []
    else:
        posts = []

    updated = False

    # Add IDs where missing
    for post in posts:
        if 'id' not in post:
            post['id'] = str(uuid.uuid4())
            updated = True

    # Save if updated
    if updated:
        with open(POST_FILE, "w") as f:
            json.dump(posts, f, indent=4)

    return updated

def time_ago(timestamp):
    try:
        post_time = datetime.fromisoformat(timestamp)
    except ValueError:
        try:
            post_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return "unknown"

    diff = datetime.now() - post_time
    seconds = diff.total_seconds()

    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds//60)}m"
    elif seconds < 86400:
        return f"{int(seconds//3600)}h"
    elif seconds < 604800:
        return f"{int(seconds//86400)}d"
    else:
        return post_time.strftime("%b %d, %Y")
def get_current_user():
    """Return the logged-in user dict from users.json or None if not found."""
    users = load_json(USER_FILE)

    # Support both old and new session formats
    code = session.get('username') or session.get('user', {}).get('code')

    if not code:
        return None

    # Find matching user in the list
    return next((u for u in users if u.get('code') == code), None)

def create_notification(user_code, title, message, category='info', extra_data=None):
    notifications = load_json(NOTIFICATION_FILE)
    if not isinstance(notifications, list):
        notifications = []

    notification = {
        "id": str(uuid.uuid4()),
        "user_code": user_code,
        "title": title,
        "message": message,
        "category": category,
        "extra_data": extra_data or {},
        "timestamp": datetime.now().isoformat(),
        "read": False
    }

    notifications.append(notification)
    save_json(NOTIFICATION_FILE, notifications)

def format_timestamp(iso_time):
    delta = datetime.now() - datetime.fromisoformat(iso_time)
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds} seconds ago"
    elif seconds < 3600:
        return f"{seconds // 60} minutes ago"
    elif seconds < 86400:
        return f"{seconds // 3600} hours ago"
    if updated:
        with open("posts.json", "w") as f:
            json.dump(posts, f, indent=4)
        print("✅ Missing post IDs assigned and saved.")
    else:
        print("✅ All posts already have IDs.")

def resize_image(image_path, max_size=(300, 300)):
    """Resize image to maximum dimensions while maintaining aspect ratio"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            img.save(image_path, optimize=True)
    except Exception as e:
        print(f"Error resizing image: {e}")

@app.context_processor
def inject_now():
    return {'datetime': datetime}

# WebSocket events
@socketio.on('connect')
def on_connect():
    if 'username' in session:
        join_room(session['username'])
        emit('status', {'msg': f'{session["username"]} has connected'})

@socketio.on('disconnect')
def on_disconnect():
    if 'username' in session:
        leave_room(session['username'])

@socketio.on('send_message')
def handle_message(data):
    if 'username' not in session:
        return
    
    users = load_json(USER_FILE)
    messages = load_json(MESSAGE_FILE)
    sender = users[session['username']]
    
    message = {
        'id': str(uuid.uuid4()),
        'sender_id': session['username'],
        'sender_name': sender['full_name'],
        'receiver_id': data['receiver_id'],
        'content': data['content'],
        'timestamp': datetime.now().isoformat(),
        'read': False
    }
    
    messages.setdefault('conversations', []).append(message)
    save_json(MESSAGE_FILE, messages)
    
    # Emit to receiver
    emit('new_message', message, room=data['receiver_id'])
    
    # Create notification
    create_notification(
        data['receiver_id'], 
        'New Message', 
        f'You have a new message from {sender["full_name"]}',
        'info',
        {'message_id': message['id']}
    )
fix_missing_post_ids()
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login first.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def save_posts(posts):
    with open(POST_FILE, 'w') as f:
        json.dump(posts, f, indent=4)
def load_posts():
    if os.path.exists(POST_FILE):
        with open(POST_FILE, 'r') as f:
            return json.load(f)
    return []
def load_users():
    try:
        with open('users.json') as f:
            return json.load(f)
    except FileNotFoundError:
        return []  # Return empty list if users.json does not exist
def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []
def get_logged_in_user():
    code = session.get("code")
    if not code:
        return None
    users = load_users()
    for user in users:
        if user.get("code") == code:
            return user
    return None
def save_data(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)
def get_logged_in_user():
    if 'username' in session and 'code' in session:
        users = load_users()
        return next((u for u in users if u['username'] == session['username'] and u['code'] == session['code']), None)
    return None
def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# ======= Helper Functions =======

def time_since(timestamp):
    now = datetime.utcnow()
    diff = now - datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

    seconds = diff.total_seconds()
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        return f"{int(seconds // 60)} mins ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)} hrs ago"
    elif seconds < 604800:
        return f"{int(seconds // 86400)} days ago"
    else:
        return timestamp.split(' ')[0]  # Show date only
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return []

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def get_user(code):
    users = load_json('users.json')
    for user in users:
        if user['code'] == code:
            return user
    return None

def timeago(timestamp):
    now = datetime.now()
    delta = relativedelta(now, timestamp)
    if delta.years > 0:
        return f"{delta.years} year(s) ago"
    elif delta.months > 0:
        return f"{delta.months} month(s) ago"
    elif delta.days > 0:
        return f"{delta.days} day(s) ago"
    elif delta.hours > 0:
        return f"{delta.hours} hour(s) ago"
    elif delta.minutes > 0:
        return f"{delta.minutes} minute(s) ago"
    else:
        return "just now"

app.jinja_env.filters['timeago'] = timeago
def filter_posts(user):
    posts = load_json('posts.json')
    filtered = []
    for post in posts:
        if post['archdiocese'] == user['archdiocese'] and \
           post['diocese'] == user['diocese'] and \
           post['denary'] == user['denary'] and \
           post['parish'] == user['parish'] and \
           post['local_church'] == user['local_church']:
            filtered.append(post)
    return sorted(filtered, key=lambda x: x.get('timestamp', ''), reverse=True)
def in_jurisdiction(post):
    if post['target_level'] == 'local_church':
        return post['local_church'] == current_user['local_church']
    elif post['target_level'] == 'parish':
        return post['parish'] == current_user['parish']
    elif post['target_level'] == 'denary':
        return post['denary'] == current_user['denary']
    elif post['target_level'] == 'diocese':
        return post['diocese'] == current_user['diocese']
    elif post['target_level'] == 'archdiocese':
        return post['archdiocese'] == current_user['archdiocese']
    return False

# ======= Routes =======
@app.template_filter('format_timestamp')
def format_timestamp_filter(timestamp):
    try:
        timestamp_dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        now = datetime.utcnow()
        delta = relativedelta(now, timestamp_dt)

        if delta.years > 0:
            return f"{delta.years} year(s) ago"
        elif delta.months > 0:
            return f"{delta.months} month(s) ago"
        elif delta.days > 0:
            return f"{delta.days} day(s) ago"
        elif delta.hours > 0:
            return f"{delta.hours} hour(s) ago"
        elif delta.minutes > 0:
            return f"{delta.minutes} minute(s) ago"
        else:
            return "Just now"
    except:
        return timestamp
@app.route('/')
def home():
    return redirect('/login')

def index():
    return redirect(url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Create form instance
    form = LoginForm()
    
    if form.validate_on_submit():  # Handles POST and validation
        code = form.username.data.strip()  # Using username field for member code
        password = form.password.data.strip()

        # Load users
        try:
            with open('users.json', 'r') as f:
                users = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            users = []

        # Find matching user
        user = next((u for u in users 
                   if u.get('code') == code 
                   and u.get('password') == password), None)

        if user:
            # Set session data
            session.update({
                'username': user.get('username', code),
                'code': code,
                'user': {
                    'code': code,
                    'full_name': user['full_name'],
                    'rank': user['rank'],
                    'local_church': user['local_church'],
                    'parish': user['parish'],
                    'denary': user['denary'],
                    'diocese': user['diocese']
                }

            })
            session.permanent = True
            
            # Update last active
            user['last_active'] = datetime.now().isoformat()
            with open('users.json', 'w') as f:
                json.dump(users, f, indent=4)
            
            flash('✅ Login successful!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('❌ Invalid credentials', 'error')
    
    return render_template('login.html', form=form)  # Pass form to template

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("You have been logged out.")
    return redirect(url_for('login'))

@app.route('/chairman_dashboard')
def chairman_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    if 'chairman' not in user.get('rank', '').lower():
        return "Unauthorized access", 403

    users = load_json(USER_FILE)
    # Members in jurisdiction
    members = [
        u for u in users
        if (
            u.get('local_church') == user.get('local_church') or
            u.get('parish') == user.get('parish') or
            u.get('denary') == user.get('denary') or
            u.get('diocese') == user.get('diocese') or
            u.get('archdiocese') == user.get('archdiocese')
        )
    ]
    # Initialize stats with empty dicts to avoid Undefined
    stats = {
        'total': len(members),
        'male': sum(1 for m in members if m.get('gender', '').lower() == 'male'),
        'female': sum(1 for m in members if m.get('gender', '').lower() == 'female'),
        'disabilities': sum(1 for m in members if m.get('disability', '').strip().lower() not in ['', 'none']),
        'education': {},
        'occupation': {},
        'marital_status': {},
        'confirmation': {'Yes': 0, 'No': 0},
        'baptism': {'Yes': 0, 'No': 0},
        'departments': {}
    }
    # Loop through members to fill stats
    for m in members:
        edu = m.get('education_level', 'Unknown').strip().title()
        stats['education'][edu] = stats['education'].get(edu, 0) + 1

        occ = m.get('occupation_status', 'Unknown').strip().title()
        stats['occupation'][occ] = stats['occupation'].get(occ, 0) + 1

        marital = m.get('marital_status', 'Unknown').strip().title()
        stats['marital_status'][marital] = stats['marital_status'].get(marital, 0) + 1

        conf = m.get('confirmation', 'No').strip().title()
        if conf not in stats['confirmation']:
            stats['confirmation'][conf] = 0
        stats['confirmation'][conf] += 1

        bap = m.get('baptism', 'No').strip().title()
        if bap not in stats['baptism']:
            stats['baptism'][bap] = 0
        stats['baptism'][bap] += 1

        dept = m.get('department', 'Unknown').strip().title()
        stats['departments'][dept] = stats['departments'].get(dept, 0) + 1

    return render_template(
        'chairman_dashboard.html',
        members=members,
        stats=stats,
        user=user
    )

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))

    # Load all data files
    users = load_json(USER_FILE)
    posts = load_json(POST_FILE)
    comments = load_json(COMMENT_FILE)
    events = load_json(EVENT_FILE)
    notifications = load_json(NOTIFICATION_FILE)

    # Get current user from session
    session_user = session['user']
    code = session_user['code']

    # Find current user
    current_user = next((u for u in users if u.get('code') == code), None)
    if not current_user:
        flash("User not found.", "error")
        return redirect(url_for('login'))

    # Extract details
    full_name = current_user.get('full_name')
    rank = current_user.get('rank')
    gender = current_user.get('gender')
    dob = current_user.get('dob')
    phone = current_user.get('phone')
    email = current_user.get('email')
    local_church = current_user.get('local_church')
    parish = current_user.get('parish')
    denary = current_user.get('denary')
    diocese = current_user.get('diocese')
    archdiocese = current_user.get('archdiocese')

    # Filters
    filter_level = request.args.get('filter_level', 'all')
    filter_department = request.args.get('filter_department', 'all')
    search_query = request.args.get('search', '').lower()

    # Map rank to level
    level_map = {
        'local': 'local_church',
        'parish': 'parish',
        'denary': 'denary',
        'diocese': 'diocese',
        'archdiocese': 'archdiocese'
    }
    target_level = None
    for key, field in level_map.items():
        if rank.lower().startswith(key):
            target_level = field
            break
    # Handle new post creation
    if request.method == 'POST' and 'member' not in rank.lower():
        content = request.form['content']
        post_type = request.form.get('post_type', 'general')

        post = {
            "id": str(uuid.uuid4()),
            "author": full_name,
            "author_code": code,
            "rank": rank,
            "content": content,
            "type": post_type,
            "timestamp": datetime.now().isoformat(),
            "pinned": False,
            "likes": [],
            "target_level": target_level,
            "archdiocese": archdiocese,
            "diocese": diocese,
            "denary": denary,
            "parish": parish,
            "local_church": local_church
        }
        posts.insert(0, post)
        save_json(POST_FILE, posts)

    # Jurisdiction check
    def in_jurisdiction(post):
        target = post.get('target_level')
        if target == 'local_church':
            return post.get('local_church') == local_church
        elif target == 'parish':
            return post.get('parish') == parish
        elif target == 'denary':
            return post.get('denary') == denary
        elif target == 'diocese':
            return post.get('diocese') == diocese
        elif target == 'archdiocese':
            return post.get('archdiocese') == archdiocese
        return False

    # Filter posts
    filtered_posts = []
    for post in posts:
        if not in_jurisdiction(post):
            continue
        if filter_level != 'all' and post.get('target_level') != filter_level:
            continue
        if filter_department != 'all' and post.get('department') != filter_department:
            continue
        if search_query and search_query not in post.get('content', '').lower():
            continue
        if 'type' not in post:
            post['type'] = 'general'
        filtered_posts.append(post)

    # Sort pinned first
    filtered_posts.sort(
        key=lambda x: (not x.get('pinned', False), x.get('timestamp', '')),
        reverse=True
    )
    for post in filtered_posts:
       post['time_ago'] = time_ago(post.get('timestamp', ''))
    # Members list (chairman only)
    members = []
    if current_user.get('role', '').lower() == 'chairman':
        members = [
            u for u in users
            if u.get('archdiocese') == archdiocese
            and u.get('diocese') == diocese
            and u.get('denary') == denary
            and u.get('parish') == parish
            and u.get('local_church') == local_church
        ]

    # Stats
    total_members = len(members)
    male_members = sum(1 for m in members if m.get('gender') == 'Male')
    female_members = sum(1 for m in members if m.get('gender') == 'Female')

    unread_notifications = sum(
        1 for n in notifications
        if n.get('user_code') == code and not n.get('read', False)
    )

    return render_template(
        'dashboard.html',
        user=current_user,
        full_name=full_name,
        rank=rank,
        posts=filtered_posts,
        members=members,
        total_members=total_members,
        male_members=male_members,
        female_members=female_members,
        filter_level=filter_level,
        filter_department=filter_department,
        search_query=search_query,
        code=code,
        gender=gender,
        dob=dob,
        phone=phone,
        email=email,
        local_church=local_church,
        parish=parish,
        denary=denary,
        diocese=diocese,
        archdiocese=archdiocese,
        time_since=time_since,
        user_rank=rank,
        user_code=code,
        unread_notifications=unread_notifications
    )


@app.route('/members')
def members():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    if user['rank'] != 'chairman':
        flash("Access denied.")
        return redirect(url_for('dashboard'))

    all_users = load_json('users.json')
    same_jurisdiction = [
        u for u in all_users if
        u['archdiocese'] == user['archdiocese'] and
        u['diocese'] == user['diocese'] and
        u['denary'] == user['denary'] and
        u['parish'] == user['parish'] and
        u['local_church'] == user['local_church']
    ]
    return render_template('members.html', user=user, members=same_jurisdiction)

@app.route('/filter', methods=['GET'])
def filter_view():
    selected_level = request.args.get('level')         # e.g., 'parish'
    selected_department = request.args.get('department')  # e.g., 'secretary'

    with open('users.json') as f:
        users = json.load(f)

    current_user = session.get('user')  # or use your loaded user object
    filtered_users = []

    for user in users:
        # Check same jurisdiction at selected level
        level_match = (
            selected_level == 'local' and user['local_church'] == current_user['local_church'] or
            selected_level == 'parish' and user['parish'] == current_user['parish'] or
            selected_level == 'denary' and user['denary'] == current_user['denary'] or
            selected_level == 'diocese' and user['diocese'] == current_user['diocese'] or
            selected_level == 'archdiocese' and user['archdiocese'] == current_user['archdiocese']
        )
        # Check if department (e.g. secretary, chaplain) is in their rank
        department_match = selected_department.lower() in user['rank'].lower()

        if level_match and department_match:
            filtered_users.append(user)

    return render_template('filtered_members.html', users=filtered_users, level=selected_level, department=selected_department)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = load_data(USER_FILE)
        form = request.form

        # Auto-generate unique 5-character code
        existing_codes = {u['code'] for u in data}
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            if code not in existing_codes:
                break
        # Extract form fields
        full_name = form['full_name']
        password = form['password']
        phone = form['phone']
        gender = form['gender']
        level = form['level']
        email = form['email']
        role = form['role']
        rank = f"{level} {role}".lower()

        birth_day = int(form.get('birth_day'))
        birth_month = int(form.get('birth_month'))
        birth_year = int(form.get('birth_year'))
        dob = date(birth_year, birth_month, birth_day)

        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        print("User age is:", age)

        # Optional fields
        local_church = form.get('local_church', '')
        parish = form.get('parish', '')
        denary = form.get('denary', '')
        diocese = form.get('diocese', '')
        archdiocese = form.get('archdiocese', '')
        baptism = form.get('baptism', '')
        confirmation = form.get('confirmation', '')
        marital_status = form.get('marital_status', '')
        residence = form.get('residence', '')
        education_level = form.get('education_level', '')
        disability = form.get('disability', '')
        occupation_status = form.get('occupation_status', '')
        institution_type = form.get('institution_type', '')
        talents = form.get('talents', '')
        bio = form.get('bio', '')

        # Check leader uniqueness (if required)
        if role in ['chairman', 'secretary', 'treasurer', 'chaplain', 'matron', 'patron', 'organising secretary']:
            for u in data:
                if u['rank'] == rank:
                    if (level == 'local' and u['local_church'] == local_church) or \
                       (level == 'parish' and u['parish'] == parish) or \
                       (level == 'denary' and u['denary'] == denary) or \
                       (level == 'diocese' and u['diocese'] == diocese) or \
                       (level == 'archdiocese' and u['archdiocese'] == archdiocese) or \
                       (level == 'international'):
                        return render_template('register.html',
                            error=f"A {rank} already exists in this jurisdiction.", 
                            form_data=form
                        )

        # Build user object
        user = {
            'id': str(uuid.uuid4()),
            'full_name': full_name,
            'code': code,
            'password': password,
            'phone': phone,
            'gender': gender,
            'email': email,
            'age': age,
            'rank': rank,
            'dob': dob.isoformat(),
            'username': code,
            'local_church': local_church,
            'parish': parish,
            'denary': denary,
            'diocese': diocese,
            'archdiocese': archdiocese,
            'residence': residence,
            'education_level': education_level,
            'disability': disability,
            'occupation_status': occupation_status,
            'institution_type': institution_type,
            'talents': talents,
            'bio': bio,
            'marital_status': marital_status,
            'confirmation': confirmation,
            'baptism': baptism,
            "profile_picture": None,
            "joined_date": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "settings": {
                "email_notifications": True,
                "push_notifications": True,
                "privacy_level": "friends"
            }
        }
        # ✅ Save user
        data.append(user)
        save_data(USER_FILE, data)
        # ✅ Send email
        try:
            send_welcome_email(
                recipient=user['email'],
                name=user['full_name'],
                code=user['code']
            )
            flash('Registration successful! Check your email for your member code', 'success')
        except Exception as e:
            flash('Registration succeeded but email failed to send', 'warning')
            print(f"Email error: {str(e)}")

        return redirect(url_for('dashboard'))

    return render_template('register.html', current_year=datetime.now().year)
    for p in visible_posts:
        p['time_ago'] = format_timestamp(p['timestamp'])
        p['comments'] = comments.get(p['id'], [])
        p['like_count'] = len(p.get('likes', []))
        p['user_liked'] = username in p.get('likes', [])
    # Get upcoming events
    upcoming_events = []
    for event in events.get('events', []):
        if is_within_boundary(event):
            event_date = datetime.fromisoformat(event['start_date'])
            if event_date >= datetime.now():
                upcoming_events.append(event)
    
    upcoming_events.sort(key=lambda e: e['start_date'])
    upcoming_events = upcoming_events[:5]  # Show next 5 events
    
    # Get unread notifications
    user_notifications = notifications.get(username, [])
    unread_count = len([n for n in user_notifications if not n['read']])

    return render_template('dashboard.html', 
                         user=user, 
                         posts=visible_posts[:10], 
                         upcoming_events=upcoming_events,
                         unread_notifications=unread_count)


@app.route('/add_comment/<post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    comment_text = request.form.get('comment')

    try:
        with open('posts.json', 'r') as f:
            posts = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        posts = []

    for post in posts:
        if post['id'] == post_id:
            new_comment = {
                "author": user['full_name'],
                "rank": user['rank'],
                "content": comment_text,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            post['comments'].append(new_comment)
            break

    with open('posts.json', 'w') as f:
        json.dump(posts, f, indent=2)

    return redirect(url_for('view_post', post_id=post_id))

@app.route('/comment/<post_id>', methods=['POST'])
def comment(post_id):
    if 'username' not in session:
        return redirect('/login')
    
    try:
        users = load_json(USER_FILE)
        comments = load_json(COMMENT_FILE)
        
        # Initialize comments structure if not exists
        if post_id not in comments:
            comments[post_id] = []
            
        user = users[session['username']]
        content = request.form.get('comment', '').strip()
        
        if not content:
            flash('Comment cannot be empty', 'error')
            return redirect(request.referrer or url_for('view_post', post_id=post_id))
            
        comment = {
            "id": str(uuid.uuid4()),  # Add unique ID for each comment
            "author": user['full_name'],
            "author_code": user['code'],  # Store author reference
            "text": content,
            "timestamp": datetime.now().isoformat()
        }
        
        comments[post_id].append(comment)
        save_json(COMMENT_FILE, comments)
        
        flash('Comment added successfully', 'success')
        return redirect(url_for('view_post', post_id=post_id))
        
    except Exception as e:
        app.logger.error(f"Error adding comment: {str(e)}")
        flash('Error adding comment', 'error')
        return redirect(url_for('index'))

@app.route('/comments/<post_id>')
def view_comments(post_id):
    user = get_logged_in_user()
    if not user:
        return redirect(url_for('login'))

    try:
        posts = load_posts()
        post = next((p for p in posts if p['id'] == post_id), None)
        if not post:
            return "Post not found", 404

        comments = load_json(COMMENT_FILE).get(post_id, [])
        
        # Modified authorization - at least let comment authors see their comments
        can_view = (post['author_code'] == user['code'] or 
                   any(c['author_code'] == user['code'] for c in comments))
        
        if not can_view:
            return "You are not allowed to view comments for this post.", 403

        return render_template('view_comments.html', 
                             post=post, 
                             comments=comments,
                             user=user)
        
    except Exception as e:
        app.logger.error(f"Error viewing comments: {str(e)}")
        return "An error occurred", 500

@app.route('/edit_member/<user_code>', methods=['GET', 'POST'])
def edit_member(user_code):
    with open('users.json', 'r') as f:
        users = json.load(f)

    user = next((u for u in users if u['code'] == user_code), None)
    if not user:
        flash("User not found", "error")
        return redirect(url_for('view_my_details'))

    if request.method == 'POST':
        # Update all fields from form
        user['full_name'] = request.form['full_name']
        user['phone'] = request.form['phone']
        user['gender'] = request.form['gender']
        user['age'] = request.form['age']
        user['rank'] = request.form['rank']
        user['local_church'] = request.form['local_church']
        user['parish'] = request.form['parish']
        user['denary'] = request.form['denary']
        user['diocese'] = request.form['diocese']
        user['archdiocese'] = request.form['archdiocese']
        user['dob'] = request.form['dob']
        user['residence'] = request.form['residence']
        user['education_level'] = request.form['education_level']
        user['disability'] = request.form['disability']
        user['occupation_status'] = request.form['occupation_status']
        user['institution_type'] = request.form['institution_type']
        user['talents'] = request.form['talents']
        user['skills'] = request.form['skills']

        # Save the updated list back to JSON
        with open('users.json', 'w') as f:
            json.dump(users, f, indent=4)

        flash("User updated successfully", "success")
        return redirect(url_for('view_my_details'))

    return render_template('edit_member.html', user=user)
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_code' not in session:
        return redirect(url_for('login'))

    user_code = session['user_code']
    with open('users.json', 'r') as f:
        users = json.load(f)

    user = next((u for u in users if u['code'] == user_code), None)

    if not user:
        flash("User not found.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if current_password != user['password']:
            flash("Current password is incorrect.")
        elif new_password != confirm_password:
            flash("New passwords do not match.")
        elif current_password == new_password:
            flash("New password must be different from the current one.")
        else:
            user['password'] = new_password
            with open('users.json', 'w') as f:
                json.dump(users, f, indent=2)
            flash("Password changed successfully.")
            return redirect(url_for('view_my_details'))

    return render_template('change_password.html')

@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    if 'user_code' not in session:
        return redirect(url_for('login'))

    user_code = session['user_code']
    users = load_users()

    user = next((u for u in users if u['code'] == user_code), None)
    if not user:
        flash("User not found.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Update only editable fields
        editable_fields = ['fullname', 'phone', 'residence', 'gender', 'age', 'dob', 'education_level', 'disability', 'occupation_status', 'institution_type', 'talents', 'skills']
        for field in editable_fields:
            if field in request.form:
                user[field] = request.form[field].strip()

        save_users(users)
        flash("Profile updated successfully.")
        return redirect(url_for('view_my_details'))

    return render_template('update_profile.html', user=user)

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'user' not in session:
        return redirect(url_for('login'))

    # Get fresh user data
    current_user_code = session['user'].get('code')
    user = get_user_by_code(current_user_code)
    if not user:
        flash('User data not found', 'error')
        return redirect(url_for('login'))
    # Update session with fresh data
    session['user'] = user
    rank = user.get('rank', '').lower()
    # Determine target level
    level_map = {
        'local': 'local_church',
        'parish': 'parish',
        'denary': 'denary',
        'diocese': 'diocese',
        'archdiocese': 'archdiocese'
    }
    target_level = next((field for key, field in level_map.items() if rank.startswith(key)), None)
    if not target_level or 'member' in rank:
        return "Unauthorized to post", 403

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        post_type = request.form.get('post_type', 'general')
        if not content:
            flash('Post content cannot be empty', 'error')
            return redirect(url_for('create_post'))

        # Construct post object
        post = {
            'id': str(uuid.uuid4()),
            'author': user['full_name'],
            'author_code': user['code'],
            'rank': user['rank'],
            'content': content,
            'type': post_type,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'pinned': False,
            'likes': [],
            'target_level': target_level,
            'local_church': user.get('local_church'),
            'parish': user.get('parish'),
            'denary': user.get('denary'),
            'diocese': user.get('diocese'),
            'archdiocese': user.get('archdiocese'),
            'comments': []
        }

        try:
            # Save post to JSON
            posts = load_json(POST_FILE) or []
            posts.insert(0, post)
            save_json(POST_FILE, posts)
            flash('Post created successfully!', 'success')

            # Send SMS to parish members
            parish = user.get('parish')
            if parish:
                members = get_parish_members(parish)  # return list of phone numbers
                message = f"New post in your parish:\n{content[:100]}..."
                send_sms(members, message)

        except Exception as e:
            flash(f'Error saving post or sending SMS: {str(e)}', 'error')

        return redirect(url_for('create_post'))

    # If GET, show the form with user's posts
    try:
        posts = load_json(POST_FILE) or []
        user_posts = [p for p in posts if p.get('author_code') == user['code']]
    except Exception:
        user_posts = []

    return render_template('create_post.html', user=user, user_posts=user_posts)

# ------------------ PIN POST ------------------
@app.route('/pin_post/<post_id>', methods=['POST'])
def pin_post(post_id):
    user = get_logged_in_user()
    if not user or 'code' not in user:
        flash("Please log in to pin a post.", "warning")
        return redirect(url_for('login'))

    posts = load_posts()
    for post in posts:
        if post['id'] == post_id and post['author_code'] == user['code']:
            post['pinned'] = True
        elif post['author_code'] == user['code']:
            post['pinned'] = False  # Unpin other posts from same user
    save_posts(posts)
    flash("Post pinned successfully.", "success")
    return redirect(url_for('dashboard'))


# ------------------ UNPIN POST ------------------
@app.route('/unpin_post/<post_id>', methods=['POST'])
def unpin_post(post_id):
    user = get_logged_in_user()
    if not user or 'code' not in user:
        flash("Please log in to unpin a post.", "warning")
        return redirect(url_for('login'))

    posts = load_posts()
    for post in posts:
        if post['id'] == post_id and post['author_code'] == user['code']:
            post['pinned'] = False

    save_posts(posts)
    flash("Post unpinned successfully.", "success")
    return redirect(url_for('dashboard'))


# ------------------ DELETE POST ------------------
@app.route('/delete_post/<post_id>', methods=['POST'])
def delete_post(post_id):
    user = get_logged_in_user()
    if not user or 'code' not in user:
        flash("Please log in to delete a post.", "warning")
        return redirect(url_for('login'))

    posts = load_posts()
    posts = [post for post in posts if not (post['id'] == post_id and post['author_code'] == user['code'])]

    save_posts(posts)
    flash("Post deleted successfully.", "success")
    return redirect(url_for('dashboard'))


@app.route('/like_post/<post_id>', methods=['POST'])
def like_post(post_id):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    posts = load_json(POST_FILE)
    username = session['username']
    
    for post in posts:
        if post['id'] == post_id:
            if 'likes' not in post:
                post['likes'] = []
            
            if username in post['likes']:
                post['likes'].remove(username)
                liked = False
            else:
                post['likes'].append(username)
                liked = True
            
            save_json(POST_FILE, posts)
            return jsonify({
                'liked': liked, 
                'like_count': len(post['likes'])
            })
    
    return jsonify({'error': 'Post not found'}), 404


@app.route('/rsvp_event/<event_id>', methods=['POST'])
def rsvp_event(event_id):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
# -----------------------
# Event Management Routes
# -----------------------

@app.route('/events')
def events():
    current_user = get_current_user()
    if not current_user:
        flash("Please log in to continue.", "warning")
        return redirect(url_for('login'))

    events_data = load_json(EVENT_FILE)

    def is_within_boundary(event):
        return (
            event.get('archdiocese') == current_user.get('archdiocese') and
            event.get('diocese') == current_user.get('diocese') and
            event.get('denary') == current_user.get('denary') and
            event.get('parish') == current_user.get('parish') and
            event.get('local_church') == current_user.get('local_church')
        )
    # Handle both dict-based and list-based formats
    if isinstance(events_data, dict):
        event_list = events_data.get('events', [])
    else:  # list format
        event_list = events_data

    visible_events = [e for e in event_list if is_within_boundary(e)]
    visible_events.sort(key=lambda e: e.get('start_date', ''), reverse=True)

    return render_template(
        'events.html',
        events=visible_events,
        user=current_user
    )


@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if 'user' not in session:
        return redirect('/login')

    users = load_json(USER_FILE)
    current_user = session['user']
    # Find full user record
    user = next((u for u in users if u['code'] == current_user['code']), None)
    if not user:
        flash("User not found.", "error")
        return redirect('/login')

    if 'member' in user['rank'].lower():
        flash('Only leaders can create events.', 'warning')
        return redirect('/events')

    if request.method == 'POST':
        events_data = load_json(EVENT_FILE)
        # Handle max_attendees safely
        max_attendees_raw = request.form.get('max_attendees', '').strip()
        max_attendees = int(max_attendees_raw) if max_attendees_raw.isdigit() else None

        event = {
            'id': str(uuid.uuid4()),
            'title': request.form['title'],
            'description': request.form['description'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date'],
            'location': request.form['location'],
            'created_by': user['full_name'],
            'creator_id': user['code'],
            'archdiocese': user['archdiocese'],
            'diocese': user['diocese'],
            'denary': user['denary'],
            'parish': user['parish'],
            'local_church': user['local_church'],
            'rsvp': [],
            'max_attendees': max_attendees,
            'created_at': datetime.now().isoformat()
        }

        # Store event in both dict or list formats
        if isinstance(events_data, dict):
            events_data.setdefault('events', []).append(event)
        else:
            events_data.append(event)

        save_json(EVENT_FILE, events_data)
        # Notify members in same jurisdiction
        for u in users:
            if u['code'] != user['code'] and (
                u['archdiocese'] == user['archdiocese'] and
                u['diocese'] == user['diocese'] and
                u['denary'] == user['denary'] and
                u['parish'] == user['parish'] and
                u['local_church'] == user['local_church']
            ):
                create_notification(
                    u['code'],
                    'New Event',
                    f'New event: {event["title"]} on {event["start_date"]}',
                    'info',
                    {'event_id': event['id']}
                )

        flash('Event created successfully!', 'success')
        return redirect('/events')

    return render_template('create_event.html', user=user)
# Profile Management
@app.route('/profile/<username>')
def view_profile(username):
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    posts = load_json(POST_FILE)
    
    if username not in users:
        flash('User not found.')
        return redirect('/dashboard')
    
    profile_user = users[username]
    current_user = users[session['username']]
    
    # Check if users are in same boundary
    def is_within_boundary():
        return (
            profile_user['archdiocese'] == current_user['archdiocese'] and
            profile_user['diocese'] == current_user['diocese'] and
            profile_user['denary'] == current_user['denary'] and
            profile_user['parish'] == current_user['parish'] and
            profile_user['local_church'] == current_user['local_church']
        )
    
    if not is_within_boundary() and session['username'] != username:
        flash('You can only view profiles of members in your organization.')
        return redirect('/dashboard')
    
    # Get user's posts
    user_posts = [p for p in posts if p['username'] == username]
    user_posts.sort(key=lambda p: p['timestamp'], reverse=True)
    
    for p in user_posts:
        p['time_ago'] = format_timestamp(p['timestamp'])
        p['like_count'] = len(p.get('likes', []))
    
    return render_template('profile.html', 
                         profile_user=profile_user, 
                         current_user=current_user,
                         posts=user_posts[:10])

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    user = users[session['username']]
    
    if request.method == 'POST':
        # Update user info
        user['full_name'] = request.form['full_name']
        user['email'] = request.form['email']
        user['phone'] = request.form['phone']
        user['bio'] = request.form['bio']
        
        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{session['username']}_{file.filename}")
                file_path = os.path.join('uploads/profiles', filename)
                file.save(file_path)
                resize_image(file_path)
                user['profile_picture'] = filename
        
        # Update settings
        user['settings'] = {
            'email_notifications': 'email_notifications' in request.form,
            'push_notifications': 'push_notifications' in request.form,
            'privacy_level': request.form.get('privacy_level', 'friends')
        }
        
        save_json(USER_FILE, users)
        flash('Profile updated successfully!')
        return redirect(f'/profile/{session["username"]}')
    
    return render_template('edit_profile.html', user=user)


# Messaging System
@app.route('/messages')
def messages():
    current_user = get_current_user()
    if not current_user:
        flash("Please log in to continue.", "warning")
        return redirect(url_for('login'))

    users = load_json(USER_FILE)
    messages_data = load_json(MESSAGE_FILE)

    # Handle both dict-based and list-based message storage
    if isinstance(messages_data, dict):
        user_messages = messages_data.get('conversations', [])
    else:
        user_messages = messages_data

    conversations = {}

    for msg in user_messages:
        if msg.get('sender_id') == current_user['code'] or msg.get('receiver_id') == current_user['code']:
            other_user_id = msg['receiver_id'] if msg['sender_id'] == current_user['code'] else msg['sender_id']

            # Find other user in list
            other_user = next((u for u in users if u.get('code') == other_user_id), {})

            if other_user_id not in conversations:
                conversations[other_user_id] = {
                    'user': other_user,
                    'messages': [],
                    'last_message': None,
                    'unread_count': 0
                }

            conversations[other_user_id]['messages'].append(msg)
            conversations[other_user_id]['last_message'] = msg

            if msg.get('receiver_id') == current_user['code'] and not msg.get('read', False):
                conversations[other_user_id]['unread_count'] += 1

    # Sort by last message time
    sorted_conversations = sorted(
        conversations.items(),
        key=lambda x: x[1]['last_message'].get('timestamp', ''),
        reverse=True
    )

    return render_template(
        'messages.html',
        conversations=sorted_conversations,
        user=current_user
    )
@app.route('/conversation/<other_user_id>')
def conversation(other_user_id):
    current_user = get_current_user()
    if not current_user:
        flash("Please log in to continue.", "warning")
        return redirect(url_for('login'))

    users = load_json(USER_FILE)
    messages_data = load_json(MESSAGE_FILE)

    # Find the other user
    other_user = next((u for u in users if u.get('code') == other_user_id), None)
    if not other_user:
        flash('User not found.')
        return redirect('/messages')
    # Handle both dict-based and list-based message storage
    if isinstance(messages_data, dict):
        all_messages = messages_data.get('conversations', [])
    else:
        all_messages = messages_data
    # Get conversation messages
    conversation_messages = [
        msg for msg in all_messages
        if (
            (msg.get('sender_id') == current_user['code'] and msg.get('receiver_id') == other_user_id)
            or
            (msg.get('sender_id') == other_user_id and msg.get('receiver_id') == current_user['code'])
        )
    ]

    conversation_messages.sort(key=lambda m: m.get('timestamp', ''))
    # Mark messages as read
    for msg in conversation_messages:
        if msg.get('receiver_id') == current_user['code']:
            msg['read'] = True

    save_json(MESSAGE_FILE, messages_data)

    return render_template(
        'conversation.html',
        messages=conversation_messages,
        other_user=other_user,
        current_user=current_user
    )
# Prayer Requests and Testimonies
@app.route('/prayers')
def prayers():
    if 'username' not in session and 'user' not in session:
        return redirect('/login')

    users = load_json(USER_FILE)
    prayers_data = load_json(PRAYER_FILE)

    # Get user code from session
    code = session.get('username') or session.get('user', {}).get('code')

    # Find current user in list
    user = next((u for u in users if u.get('code') == code), None)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))

    def is_within_boundary(prayer):
        return (
            prayer.get('archdiocese') == user.get('archdiocese') and
            prayer.get('diocese') == user.get('diocese') and
            prayer.get('denary') == user.get('denary') and
            prayer.get('parish') == user.get('parish') and
            prayer.get('local_church') == user.get('local_church')
        )
    # Handle both dict-based and list-based formats
    if isinstance(prayers_data, dict):
        requests_list = prayers_data.get('requests', [])
        testimonies_list = prayers_data.get('testimonies', [])
    else:  # list format
        requests_list = [p for p in prayers_data if p.get('type') == 'request']
        testimonies_list = [p for p in prayers_data if p.get('type') == 'testimony']

    prayer_requests = [p for p in requests_list if is_within_boundary(p)]
    testimonies = [t for t in testimonies_list if is_within_boundary(t)]

    prayer_requests.sort(key=lambda p: p.get('timestamp', ''), reverse=True)
    testimonies.sort(key=lambda t: t.get('timestamp', ''), reverse=True)

    for item in prayer_requests + testimonies:
        if 'timestamp' in item:
            item['time_ago'] = format_timestamp(item['timestamp'])

    return render_template(
        'prayers.html',
        prayer_requests=prayer_requests,
        testimonies=testimonies,
        user=user
    )


@app.route('/add_prayer', methods=['POST'])
def add_prayer():
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    prayers = load_json(PRAYER_FILE)
    # Get user code from session (support both old and new format)
    code = session.get('username') or session.get('user', {}).get('code')
    # Find current user in list
    user = next((u for u in users if u.get('code') == code), None)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    
    prayer_type = request.form['type']  # 'request' or 'testimony'
    content = request.form['content']
    anonymous = 'anonymous' in request.form
    
    prayer = {
        'id': str(uuid.uuid4()),
        'content': content,
        'author': 'Anonymous' if anonymous else user['full_name'],
        'author_id': session['username'],
        'anonymous': anonymous,
        'timestamp': datetime.now().isoformat(),
        'archdiocese': user['archdiocese'],
        'diocese': user['diocese'],
        'denary': user['denary'],
        'parish': user['parish'],
        'local_church': user['local_church'],
        'prayers_count': 0 if prayer_type == 'request' else None
    }
    
    key = 'requests' if prayer_type == 'request' else 'testimonies'
    prayers.setdefault(key, []).append(prayer)
    save_json(PRAYER_FILE, prayers)
    
    flash(f'{"Prayer request" if prayer_type == "request" else "Testimony"} shared successfully!')
    return redirect('/prayers')

@app.route('/pray_for/<prayer_id>', methods=['POST'])
def pray_for(prayer_id):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    prayers = load_json(PRAYER_FILE)
    
    # Get user code from session (support both old and new format)
    code = session.get('username') or session.get('user', {}).get('code')
    # Find current user in list
    user = next((u for u in users if u.get('code') == code), None)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))

    for prayer in prayers.get('requests', []):
        if prayer['id'] == prayer_id:
            prayer['prayers_count'] = prayer.get('prayers_count', 0) + 1
            save_json(PRAYER_FILE, prayers)
            return jsonify({'prayers_count': prayer['prayers_count']})
    
    return jsonify({'error': 'Prayer request not found'}), 404

# Notifications
@app.route('/notifications')
def notifications():
    current_user = get_current_user()
    if not current_user:
        flash("Please log in to continue.", "warning")
        return redirect(url_for('login'))

    notifications_data = load_json(NOTIFICATION_FILE)
    code = current_user['code']
    # Handle both dict-based and list-based formats
    if isinstance(notifications_data, dict):
        user_notifications = notifications_data.get(code, [])
    else:  # list format
        user_notifications = [n for n in notifications_data if n.get('user_code') == code]
    # Sort newest first
    user_notifications.sort(key=lambda n: n.get('timestamp', ''), reverse=True)
    # Add "time ago" field
    for notification in user_notifications:
        if 'timestamp' in notification:
            notification['time_ago'] = format_timestamp(notification['timestamp'])

    return render_template(
        'notifications.html',
        notifications=user_notifications
    )
@app.route('/mark_notification_read/<notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    notifications = load_json(NOTIFICATION_FILE)
    user_notifications = notifications.get(session['username'], [])
    
    for notification in user_notifications:
        if notification['id'] == notification_id:
            notification['read'] = True
            save_json(NOTIFICATION_FILE, notifications)
            return jsonify({'success': True})
    
    return jsonify({'error': 'Notification not found'}), 404

@app.route('/upload_document', methods=['POST'])
def upload_document():
    if 'username' not in session:
        return redirect('/login')

    users = load_json(USER_FILE)
    if isinstance(users, list):  # Ensure users is dict
        users = {u.get("username"): u for u in users if "username" in u}

    user = users.get(session['username'])
    if not user:
        flash("User not found.", "danger")
        return redirect('/documents')

    if 'member' in user['rank'].lower():
        flash('Only leaders can upload documents.', 'danger')
        return redirect('/documents')

    if 'document' not in request.files:
        flash('No file selected.', 'warning')
        return redirect('/documents')

    file = request.files['document']
    if file.filename == '':
        flash('No file selected.', 'warning')
        return redirect('/documents')

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', filename)
        file.save(file_path)
        flash('Document uploaded successfully!', 'success')
    else:
        flash('Invalid file type.', 'danger')

    return redirect('/documents')
@app.route('/view_document/<filename>')
def view_document(filename):
    if 'username' not in session:
        flash("Please log in to view documents.", "warning")
        return redirect(url_for('login'))

    return send_from_directory('uploads/documents', filename)

@app.route('/documents')
def documents():
    current_user = get_current_user()
    if not current_user:
        flash("Please log in to continue.", "warning")
        return redirect(url_for('login'))

    documents_list = []
    doc_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents')
    if os.path.exists(doc_path):
        for filename in os.listdir(doc_path):
            file_path = os.path.join(doc_path, filename)
            if os.path.isfile(file_path):
                documents_list.append({
                    'filename': filename,
                    'size': os.path.getsize(file_path),
                    'uploaded': datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
                })

    documents_list.sort(key=lambda d: d['uploaded'], reverse=True)

    return render_template(
        'documents.html',
        documents=documents_list,
        user=current_user
    )

@app.route('/delete_document/<filename>', methods=['GET', 'POST'])
def delete_document(filename):
    if 'username' not in session:
        flash("Please log in.", "warning")
        return redirect(url_for('login'))
    # Load the list of documents if you are tracking them in JSON
    docs = []
    if os.path.exists("documents.json"):
        docs = load_json("documents.json")

    doc = next((d for d in docs if d['filename'] == filename), None)
    # If not found in JSON, still try deleting from uploads folder
    if not doc:
        file_path = os.path.join('uploads/documents', filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            flash("Document deleted successfully.", "success")
        else:
            flash("Document not found.", "danger")
        return redirect(url_for('documents'))
    # Only uploader or chairman can delete
    current_user = get_current_user()
    if doc['uploader'] != session['username'] and "chairman" not in current_user['rank'].lower():
        flash("You are not allowed to delete this document.", "danger")
        return redirect(url_for('documents'))
    # Delete file from disk
    file_path = os.path.join('uploads/documents', filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    # Remove record from JSON
    docs = [d for d in docs if d['filename'] != filename]
    save_json("documents.json", docs)

    flash("Document deleted successfully.", "success")
    return redirect(url_for('documents'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Serve files from uploads folder
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(full_path):
        directory = os.path.dirname(full_path)
        file_name = os.path.basename(full_path)
        return send_from_directory(directory, file_name)
    return "File not found", 404
# Search functionality
@app.route('/search')
def search():
    if 'username' not in session:
        return redirect('/login')
    
    query = request.args.get('q', '').strip()
    results = {'posts': [], 'users': [], 'events': []}
    
    if query:
        users = load_json(USER_FILE)
        posts = load_json(POST_FILE)
        events = load_json(EVENT_FILE)
        current_user = users[session['username']]
        
        def is_within_boundary(item):
            return (
                item['archdiocese'] == current_user['archdiocese'] and
                item['diocese'] == current_user['diocese'] and
                item['denary'] == current_user['denary'] and
                item['parish'] == current_user['parish'] and
                item['local_church'] == current_user['local_church']
            )
        # Search posts
        for post in posts:
            if is_within_boundary(post) and query.lower() in post['content'].lower():
                post['time_ago'] = format_timestamp(post['timestamp'])
                results['posts'].append(post)
        # Search users
        for user_id, user_data in users.items():
            if (is_within_boundary(user_data) and 
                (query.lower() in user_data['full_name'].lower() or 
                 query.lower() in user_data.get('bio', '').lower())):
                results['users'].append(user_data)
        
        # Search events
        for event in events.get('events', []):
            if (is_within_boundary(event) and 
                (query.lower() in event['title'].lower() or 
                 query.lower() in event['description'].lower())):
                results['events'].append(event)
    
    return render_template('search.html', query=query, results=results)
@app.route('/members')
def view_members():
    if 'user' not in session:
        return redirect('/login')

    current_user = session['user']

    with open('users.json') as f:
        users = json.load(f)
    # Function to check if user is in jurisdiction
    def in_jurisdiction(u):
        # If chairman — filter based on chairman's level
        if "chairman" in current_user['rank'].lower():
            if "local" in current_user['rank'].lower():
                return u.get('local_church') == current_user.get('local_church')
            elif "parish" in current_user['rank'].lower():
                return u.get('parish') == current_user.get('parish')
            elif "denary" in current_user['rank'].lower():
                return u.get('denary') == current_user.get('denary')
            elif "diocese" in current_user['rank'].lower():
                return u.get('diocese') == current_user.get('diocese')
            elif "archdiocese" in current_user['rank'].lower():
                return u.get('archdiocese') == current_user.get('archdiocese')

        else:
            # Non-chairman sees only same jurisdiction
            return (
                u.get('local_church') == current_user.get('local_church') and
                u.get('parish') == current_user.get('parish') and
                u.get('denary') == current_user.get('denary') and
                u.get('diocese') == current_user.get('diocese') and
                u.get('archdiocese') == current_user.get('archdiocese')
            )
        return False

    members_in_jurisdiction = [u for u in users if in_jurisdiction(u)]
    # --- Statistics ---
    stats = {
        "total": len(members_in_jurisdiction),
        "male": sum(1 for u in members_in_jurisdiction if u.get('gender') == 'male'),
        "female": sum(1 for u in members_in_jurisdiction if u.get('gender') == 'female'),
        "education": {},
        "disabilities": sum(1 for u in members_in_jurisdiction if u.get('disability', '').strip().lower() not in ['', 'none']),
        "age_groups": {"under_18": 0, "18_25": 0, "26_40": 0, "above_40": 0},
        "departments": {}
    }

    for u in members_in_jurisdiction:
        # Education
        edu = u.get('education_level', 'Unknown')
        stats['education'][edu] = stats['education'].get(edu, 0) + 1
        # Age group
        try:
            age = int(u.get('age', 0))
            if age < 18:
                stats['age_groups']["under_18"] += 1
            elif 18 <= age <= 25:
                stats['age_groups']["18_25"] += 1
            elif 26 <= age <= 40:
                stats['age_groups']["26_40"] += 1
            else:
                stats['age_groups']["above_40"] += 1
        except ValueError:
            pass
        # Departments
        dept = u.get('department', 'Unknown')
        stats['departments'][dept] = stats['departments'].get(dept, 0) + 1

    return render_template('members.html', members=members_in_jurisdiction, stats=stats)

@app.route('/view_my_details')
def view_my_details():
    user = session.get('user')
    if not user:
        return redirect('/login')

    with open('users.json') as f:
        users = json.load(f)

    user_data = next((u for u in users if u['code'] == user['code']), None)

    if not user_data:
        return "User details not found", 404
    # Convert registration_date from string to datetime
    if 'registration_date' in user_data and isinstance(user_data['registration_date'], str):
        try:
            user_data['registration_date'] = datetime.fromisoformat(user_data['registration_date'])
        except ValueError:
            pass  # Leave it as string if parsing fails
    return render_template('view_my_details.html', user=user_data)

@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')

@app.route('/add_member', methods=['GET', 'POST'])
def add_member():
    if 'username' not in session:
        return redirect('/login')

    users = load_json(USER_FILE)
    current_user = users[session['username']]

    if 'chairman' not in current_user['rank'].lower():
        flash('Only chairmen can add members.')
        return redirect('/dashboard')

    if request.method == 'POST':
        new_username = str(uuid.uuid4())[:8]
        new_user = {
            "full_name": request.form['full_name'],
            "username": new_username,
            "password": request.form['password'],
            "age": request.form['age'],
            "rank": request.form['rank'],
            "local_church": current_user['local_church'],
            "parish": current_user['parish'],
            "denary": current_user['denary'],
            "diocese": current_user['diocese'],
            "archdiocese": current_user['archdiocese'],
            "email": request.form.get('email', ''),
            "phone": request.form.get('phone', ''),
            "bio": '',
            "profile_picture": None,
            "joined_date": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "settings": {
                "email_notifications": True,
                "push_notifications": True,
                "privacy_level": "friends"
            }
        }
        users[new_username] = new_user
        save_json(USER_FILE, users)
        flash(f"Added user. Username: {new_username}")
        return redirect('/dashboard')

    return render_template('add_member.html', user=current_user)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
