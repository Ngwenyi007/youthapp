from flask import Flask, render_template, send_from_directory, request, redirect, session, flash, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid, json, os, re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import base64
from PIL import Image
import io
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from dateutil.relativedelta import relativedelta  # Usisahau hii
import random
import string
from functools import wraps
import fcntl



app = Flask(__name__)
app.secret_key = 'youth_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize SocketIO for real-time features
socketio = SocketIO(app, cors_allowed_origins="*")

# Create upload directories
os.makedirs('uploads/profiles', exist_ok=True)
os.makedirs('uploads/documents', exist_ok=True)
os.makedirs('uploads/events', exist_ok=True)

USER_FILE = 'users.json'
POST_FILE = 'posts.json'
COMMENT_FILE = 'comments.json'
EVENT_FILE = 'events.json'
NOTIFICATION_FILE = 'notifications.json'
MESSAGE_FILE = 'messages.json'
PRAYER_FILE = 'prayers.json'
ATTENDANCE_FILE = 'attendance.json'

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
username = "code"
# Upload folder configuration
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'events'), exist_ok=True)
# 🧠 Automatically adds "organising secretary" to all levels
role_definitions = {
    'Local': ['member', 'chairman', 'secretary', 'organising secretary', 'chaplain', 'matron', 'patron', 'treasurer'],
    'Parish': ['chaplain', 'chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer'],
    'Denary': ['chaplain', 'chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer'],
    'Diocese': ['chaplain', 'chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer'],
    'National': ['chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer']
}
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
def get_current_user():
    """Return the logged-in user dict from users.json or None if not found."""
    users = load_json(USER_FILE)

    # Support both old and new session formats
    code = session.get('username') or session.get('user', {}).get('code')

    if not code:
        return None

    # Find matching user in the list
    return next((u for u in users if u.get('code') == code), None)

def create_notification(user_id, title, message, type='info', data=None):
    """Create a notification for a user"""
    notifications = load_json(NOTIFICATION_FILE)
    notification = {
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'title': title,
        'message': message,
        'type': type,  # info, success, warning, error
        'data': data or {},
        'timestamp': datetime.now().isoformat(),
        'read': False
    }
    notifications.setdefault(user_id, []).append(notification)
    save_json(NOTIFICATION_FILE, notifications)
    
    # Emit real-time notification
    socketio.emit('new_notification', notification, room=user_id)
    return notification

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
    with open(POSTS_FILE, 'w') as f:
        json.dump(posts, f, indent=4)
def load_posts():
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, 'r') as f:
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

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# ======= Helper Functions =======
from datetime import datetime

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
        if post['diocese'] == user['diocese'] and \
           post['denary'] == user['denary'] and \
           post['parish'] == user['parish'] and \
           post['local_church'] == user['local_church']:
            filtered.append(post)
    return sorted(filtered, key=lambda x: x.get('timestamp', ''), reverse=True)

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
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        password = request.form.get('password', '').strip()

        # Load users from JSON
        try:
            with open('users.json', 'r') as f:
                users = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            users = []

        # Search for matching user
        for user in users:
            if user.get('code') == code and user.get('password') == password:
                # ✅ Store both for compatibility
                session['username'] = user['code']
                session['user'] = {
                    'code': user['code'],
                    'full_name': user['full_name'],
                    'rank': user['rank'],
                    'local_church': user['local_church'],
                    'parish': user['parish'],
                    'denary': user['denary'],
                    'diocese': user['diocese']
                }
                session.permanent = True

                # Update last active
                user['last_active'] = datetime.now().isoformat()
                with open('users.json', 'w') as f:
                    json.dump(users, f, indent=4)

                flash('✅ Login successful!', 'success')
                return redirect(url_for('dashboard'))

        flash('❌ Invalid code or password.', 'error')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("You have been logged out.")
    return redirect(url_for('login'))

@app.route('/chairmans')
def chairman_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    if 'chairman' not in user.get('rank', '').lower():
        return "Unauthorized access", 403

    with open('users.json') as f:
        users = json.load(f)

    members = []
    for u in users:
        # Check if user is in same jurisdiction as chairman
        if (
            u.get('local_church') == user.get('local_church') or
            u.get('parish') == user.get('parish') or
            u.get('denary') == user.get('denary') or
            u.get('diocese') == user.get('diocese')
        ):
            members.append(u)

    # Stats calculation
    stats = {
        'total': len(members),
        'male': sum(1 for m in members if m.get('gender', '').lower() == 'male'),
        'female': sum(1 for m in members if m.get('gender', '').lower() == 'female'),
        'education': {},
        'disabilities': sum(1 for m in members if m.get('disability', '').strip().lower() not in ['no', '', 'none']),
        'departments': {}
    }

    for m in members:
        edu = m.get('education', 'unknown').strip().lower()
        stats['education'][edu] = stats['education'].get(edu, 0) + 1

        dept = m.get('department', 'unknown').strip().lower()
        stats['departments'][dept] = stats['departments'].get(dept, 0) + 1

    return render_template('chairman_dashboard.html', members=members, stats=stats, user=user)




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

    # Find current user in JSON list
    current_user = next((u for u in users if u.get('code') == code), None)
    if not current_user:
        flash("User not found.", "error")
        return redirect(url_for('login'))

    # Extract user details
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

    # Filters
    filter_level = request.args.get('filter_level', 'all')
    filter_department = request.args.get('filter_department', 'all')
    search_query = request.args.get('search', '').lower()

    # Determine jurisdiction level
    user_level = None
    for level in ['local_church', 'parish', 'denary', 'diocese']:
        if current_user.get(level):
            user_level = level
            break

    # Handle new post creation
    if request.method == 'POST' and 'member' not in rank.lower():
        content = request.form['content']
        post_type = request.form.get('post_type', 'general')

        post = {
            "id": str(uuid.uuid4()),
            "author": full_name,
            "username": code,
            "content": content,
            "type": post_type,
            "timestamp": datetime.now().isoformat(),
            "pinned": False,
            "likes": [],
            "diocese": diocese,
            "denary": denary,
            "parish": parish,
            "local_church": local_church
        }
        posts.insert(0, post)
        save_json(POST_FILE, posts)

        # Notify members in jurisdiction if announcement/urgent
        if post_type in ['announcement', 'urgent']:
            for u in users:
                if u['code'] != code and is_within_boundary(u):
                    create_notification(
                        u['code'],
                        f'New {post_type.title()}',
                        f'{full_name} posted: {content[:50]}...',
                        'warning' if post_type == 'urgent' else 'info',
                        {'post_id': post['id']}
                    )

    # Jurisdiction check
    def in_jurisdiction(post):
        return (
            post.get('diocese') == diocese and
            post.get('denary') == denary and
            post.get('parish') == parish and
            post.get('local_church') == local_church
        )

    # Filter posts
    filtered_posts = []
    for post in posts:
        if not in_jurisdiction(post):
            continue
        if filter_level != 'all' and post.get('level') != filter_level:
            continue
        if filter_department != 'all' and post.get('department') != filter_department:
            continue
        if search_query and search_query not in post.get('content', '').lower():
            continue
        if 'type' not in post:
            post['type'] = 'general'
        filtered_posts.append(post)

    # Sort: pinned first, then newest
    filtered_posts.sort(
        key=lambda x: (not x.get('pinned', False), x.get('timestamp', '')),
        reverse=True
    )

    # Members list (chairman only)
    members = []
    if current_user.get('role', '').lower() == 'chairman':
        members = [
            u for u in users if
            u.get('diocese') == diocese and
            u.get('denary') == denary and
            u.get('parish') == parish and
            u.get('local_church') == local_church
        ]

    # Stats
    total_members = len(members)
    male_members = sum(1 for m in members if m.get('gender') == 'Male')
    female_members = sum(1 for m in members if m.get('gender') == 'Female')

    # Count unread notifications for this user
    unread_notifications = sum(
        1 for n in notifications
        if n.get('user_code') == code and not n.get('read', False)
    )

    # ✅ Always return here, outside the loop
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
            selected_level == 'diocese' and user['diocese'] == current_user['diocese']
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

        full_name = form['full_name']
        password = form['password']
        phone = form['phone']
        gender = form['gender']
        age = form['age']
        level = form['level']
        email = form['email']
        role = form['role']
        rank = f"{level} {role}".lower()
        birth_day = form.get('birth_day')
        birth_month = form.get('birth_month')
        birth_year = form.get('birth_year')
        dob = f"{birth_day} {birth_month} {birth_year}"
        local_church = form.get('local_church', '')
        parish = form.get('parish', '')
        denary = form.get('denary', '')
        diocese = form.get('diocese', '')
        residence = form.get('residence', '')
        education_level = form.get('education_level', '')
        disability = form.get('disability', '')
        occupation_status = form.get('occupation_status', '')
        institution_type = form.get('institution_type', '')
        talents = form.get('talents', '')
        bio = form.get('bio', '')
        # Check for leader uniqueness
        if role in ['chairman', 'secretary', 'treasurer', 'chaplain', 'matron', 'patron', 'organising secretary']:
            for u in data:
                if u['rank'] == rank:
                    if (church_level == 'local' and u['local_church'] == local_church) or \
                       (church_level == 'parish' and u['parish'] == parish) or \
                       (church_level == 'denary' and u['denary'] == denary) or \
                       (church_level == 'diocese' and u['diocese'] == diocese) or \
                       (church_level == 'international'):
                        return render_template('register.html', error=f"A {rank} already exists in this jurisdiction.", form_data=form)

        user = {
            'id': str(uuid.uuid4()),  # ✅ assign unique id
            'full_name': full_name,
            'code': code,
            'password': password,
            'phone': phone,
            'gender': gender,
            'email' : email ,
            'age': age,
            'rank': rank,
            'local_church': local_church,
            'parish': parish,
            'dob': dob,
            'username':code,
            'denary': denary,
            'diocese': diocese,
            'residence': residence,
            'education_level': education_level,
            'disability': disability,
            'occupation_status': occupation_status,
            'institution_type': institution_type,
            'talents': talents,
            'bio': bio,
            "bio": bio,
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
        data.append(user)
        save_data(USER_FILE, data)
        return redirect(url_for('dashboard'))

    return render_template('register.html')

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

@app.route('/comment/<post_id>', methods=['POST'])
def comment(post_id):
    if 'username' not in session:
        return redirect('/login')
    users = load_json(USER_FILE)
    comments = load_json(COMMENT_FILE)
    user = users[session['username']]
    content = request.form['comment']
    comment = {
        "author": user['full_name'],
        "text": content,
        "timestamp": datetime.now().isoformat()
          }
@app.route('/comments/<post_id>')
def view_comments(post_id):
    user = get_logged_in_user()
    if not user:
        return redirect(url_for('login'))

    posts = load_posts()
    post = next((p for p in posts if p['id'] == post_id), None)
    if not post:
        return "Post not found", 404

    # Allow only the author to view comments
    if post['author_code'] != user['code']:
        return "You are not allowed to view comments for this post.", 403

    return render_template('view_comments.html', post=post, user=user)

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

    user = session['user']
    rank = user.get('rank', '').lower()

    level_map = {
        'local': 'local_church',
        'parish': 'parish',
        'denary': 'denary',
        'diocese': 'diocese'
    }
    target_level = None
    for level_key, level_field in level_map.items():
        if rank.startswith(level_key):
            target_level = level_field
            break

    if not target_level:
        return "Unauthorized to post", 403

    # POST request: save post
    if request.method == 'POST':
        content = request.form.get('content')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        post = {
            'id': str(uuid.uuid4()),
            'author': user['full_name'],
            'author_code': user['code'],
            'rank': user['rank'],
            'content': content,
            'timestamp': timestamp,
            'target_level': target_level,
            'local_church': user.get('local_church'),
            'parish': user.get('parish'),
            'denary': user.get('denary'),
            'diocese': user.get('diocese'),
            'pinned': False,
            'comments': []
        }

        try:
            with open('posts.json', 'r') as f:
                posts = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            posts = []

        posts.append(post)
        with open('posts.json', 'w') as f:
            json.dump(posts, f, indent=2)

        return redirect(url_for('create_post'))

    # GET request: show current user's posts
    try:
        with open('posts.json', 'r') as f:
            posts = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        posts = []

    user_posts = [p for p in posts if p['author_code'] == user['code']]

    return render_template('create_post.html', user=user, user_posts=user_posts)


@app.route('/view_post/<post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    user = get_logged_in_user()
    if not user:
        return redirect(url_for('login'))

    posts = load_posts()
    post = next((p for p in posts if p['id'] == post_id), None)
    if not post:
        return 'Post not found', 404

    # Add comment
    if request.method == 'POST':
        comment = request.form.get('comment')
        if comment:
            timestamp = datetime.now().isoformat()
            post.setdefault('comments', []).append({
                'author': user['full_name'],
                'rank': user['rank'],
                'church': user.get('local_church'),
                'timestamp': timestamp,
                'content': comment
            })
            save_posts(posts)
            return redirect(url_for('view_post', post_id=post_id))
    return render_template('view_post.html', user=user, post=post)


@app.route('/pin_post/<post_id>', methods=['POST'])
def pin_post(post_id):
    user = get_logged_in_user()
    if not user or 'code' not in user:
        return redirect(url_for('login'))  # Or show 403 error

    posts = load_posts()

    for post in posts:
        if post['id'] == post_id and post['author_code'] == user['code']:
            post['pinned'] = True
        elif post['author_code'] == user['code']:
            post['pinned'] = False  # Unpin all other posts from same user

    save_posts(posts)
    return redirect(url_for('dashboard'))

@app.route('/unpin_post/<post_id>', methods=['POST'])
def unpin_post(post_id):
    user = get_logged_in_user()
    posts = load_posts()
    for post in posts:
        if post['id'] == post_id and post['code'] == user['code']:
            post['pinned'] = False
    save_posts(posts)
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/delete_post/<post_id>', methods=['POST'])
def delete_post(post_id):
    user = get_logged_in_user()
    if not user or 'code' not in user:
        return redirect(url_for('login'))

    posts = load_posts()
    posts = [post for post in posts if not (post['id'] == post_id and post['author_code'] == user['code'])]
    save_posts(posts)

    return redirect(url_for('dashboard'))

@app.route('/add_comment/<post_id>', methods=['POST'])
def add_comment(post_id):
    user = get_current_user()
    comment_text = request.form['comment']
    posts = load_json('posts.json')
    for post in posts:
        if post['id'] == post_id:
            if 'comments' not in post:
                post['comments'] = []
            post['comments'].append({
                'user': user['name'],
                'text': comment_text,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            break
    save_json('posts.json', posts)
    return redirect(url_for('view_posts.html'))

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
        else:
            # Non-chairman sees only same jurisdiction
            return (
                u.get('local_church') == current_user.get('local_church') and
                u.get('parish') == current_user.get('parish') and
                u.get('denary') == current_user.get('denary') and
                u.get('diocese') == current_user.get('diocese')
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

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)

