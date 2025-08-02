from flask import Flask, render_template, request, redirect, session, flash, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid, json, os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import base64
from PIL import Image
import io

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_json(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except:
        return {} if file != POST_FILE else []

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

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
    else:
        return f"{seconds // 86400} days ago"

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

@app.route('/')
def home():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = load_json(USER_FILE)

        full_name = request.form['full_name']
        age = request.form['age']
        local_church = request.form['local_church']
        parish = request.form['parish']
        denary = request.form['denary']
        diocese = request.form['diocese']
        rank = request.form['rank']
        password = request.form['password']
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')
        bio = request.form.get('bio', '')

        # Enforce one leader per rank per church level (except member)
        if rank.lower() != 'member':
            for u in users.values():
                if (
                    u['rank'].lower() == rank.lower() and
                    u['diocese'] == diocese and
                    u['denary'] == denary and
                    u['parish'] == parish and
                    u['local_church'] == local_church
                ):
                    return f"{rank} already exists in this location. Only one leader allowed per position."

        username = str(uuid.uuid4())[:8]
        users[username] = {
            "full_name": full_name,
            "age": age,
            "local_church": local_church,
            "parish": parish,
            "denary": denary,
            "diocese": diocese,
            "rank": rank,
            "password": password,
            "username": username,
            "email": email,
            "phone": phone,
            "bio": bio,
            "profile_picture": None,
            "joined_date": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "settings": {
                "email_notifications": True,
                "push_notifications": True,
                "privacy_level": "friends"
            }
        }

        save_json(USER_FILE, users)
        session['username'] = username
        
        # Create welcome notification
        create_notification(
            username, 
            'Welcome!', 
            f'Welcome to the Youth App, {full_name}! Complete your profile to get started.',
            'success'
        )
        
        return redirect('/dashboard')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_json(USER_FILE)
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            session['username'] = username
            # Update last active
            users[username]['last_active'] = datetime.now().isoformat()
            save_json(USER_FILE, users)
            return redirect('/dashboard')
        else:
            flash("Invalid username or password.")
            return redirect('/login')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect('/login')

    users = load_json(USER_FILE)
    posts = load_json(POST_FILE)
    comments = load_json(COMMENT_FILE)
    events = load_json(EVENT_FILE)
    notifications = load_json(NOTIFICATION_FILE)
    
    username = session['username']
    user = users[username]

    def is_within_boundary(other):
        return (
            other['diocese'] == user['diocese'] and
            other['denary'] == user['denary'] and
            other['parish'] == user['parish'] and
            other['local_church'] == user['local_church']
        )

    if request.method == 'POST' and 'member' not in user['rank'].lower():
        content = request.form['content']
        post_type = request.form.get('post_type', 'general')
        
        post = {
            "id": str(uuid.uuid4()),
            "author": user['full_name'],
            "username": username,
            "content": content,
            "type": post_type,  # general, announcement, urgent
            "timestamp": datetime.now().isoformat(),
            "pinned": False,
            "likes": [],
            "diocese": user['diocese'],
            "denary": user['denary'],
            "parish": user['parish'],
            "local_church": user['local_church']
        }
        posts.insert(0, post)
        save_json(POST_FILE, posts)
        
        # Notify all members in the same boundary about new post
        if post_type in ['announcement', 'urgent']:
            for u_id, u_data in users.items():
                if u_id != username and is_within_boundary(u_data):
                    create_notification(
                        u_id,
                        f'New {post_type.title()}',
                        f'{user["full_name"]} posted: {content[:50]}...',
                        'warning' if post_type == 'urgent' else 'info',
                        {'post_id': post['id']}
                    )

    # Get recent posts
    for post in posts:
        if 'timestamp' not in post:
            post['timestamp'] = datetime.now().isoformat()

    visible_posts = [p for p in posts if is_within_boundary(p)]
    visible_posts.sort(key=lambda p: (not p.get('pinned', False), p['timestamp']), reverse=True)

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
    comments.setdefault(post_id, []).append(comment)
    save_json(COMMENT_FILE, comments)
    return redirect('/dashboard')

@app.route('/edit_post/<post_id>', methods=['POST'])
def edit_post(post_id):
    posts = load_json(POST_FILE)
    for post in posts:
        if post['id'] == post_id and session['username'] == post['username']:
            post['content'] = request.form['new_content']
            break
    save_json(POST_FILE, posts)
    return redirect('/dashboard')

@app.route('/delete_post/<post_id>', methods=['POST'])
def delete_post(post_id):
    posts = load_json(POST_FILE)
    posts = [p for p in posts if p['id'] != post_id or session['username'] != p['username']]
    save_json(POST_FILE, posts)
    return redirect('/dashboard')

@app.route('/pin_post/<post_id>', methods=['POST'])
def pin_post(post_id):
    posts = load_json(POST_FILE)
    for post in posts:
        if post['id'] == post_id:
            post['pinned'] = not post.get('pinned', False)
    save_json(POST_FILE, posts)
    return redirect('/dashboard')

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

# Event Management Routes
@app.route('/events')
def events():
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    events = load_json(EVENT_FILE)
    user = users[session['username']]
    
    def is_within_boundary(event):
        return (
            event['diocese'] == user['diocese'] and
            event['denary'] == user['denary'] and
            event['parish'] == user['parish'] and
            event['local_church'] == user['local_church']
        )
    
    visible_events = [e for e in events.get('events', []) if is_within_boundary(e)]
    visible_events.sort(key=lambda e: e['start_date'])
    
    return render_template('events.html', events=visible_events, user=user)

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    user = users[session['username']]
    
    if 'member' in user['rank'].lower():
        flash('Only leaders can create events.')
        return redirect('/events')
    
    if request.method == 'POST':
        events = load_json(EVENT_FILE)
        
        event = {
            'id': str(uuid.uuid4()),
            'title': request.form['title'],
            'description': request.form['description'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date'],
            'location': request.form['location'],
            'created_by': user['full_name'],
            'creator_id': session['username'],
            'diocese': user['diocese'],
            'denary': user['denary'],
            'parish': user['parish'],
            'local_church': user['local_church'],
            'rsvp': [],
            'max_attendees': int(request.form.get('max_attendees', 0)) or None,
            'created_at': datetime.now().isoformat()
        }
        
        events.setdefault('events', []).append(event)
        save_json(EVENT_FILE, events)
        
        # Notify all members about new event
        for u_id, u_data in users.items():
            if u_id != session['username'] and (
                u_data['diocese'] == user['diocese'] and
                u_data['denary'] == user['denary'] and
                u_data['parish'] == user['parish'] and
                u_data['local_church'] == user['local_church']
            ):
                create_notification(
                    u_id,
                    'New Event',
                    f'New event: {event["title"]} on {event["start_date"]}',
                    'info',
                    {'event_id': event['id']}
                )
        
        flash('Event created successfully!')
        return redirect('/events')
    
    return render_template('create_event.html', user=user)

@app.route('/rsvp_event/<event_id>', methods=['POST'])
def rsvp_event(event_id):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    events = load_json(EVENT_FILE)
    users = load_json(USER_FILE)
    username = session['username']
    user = users[username]
    
    for event in events.get('events', []):
        if event['id'] == event_id:
            if 'rsvp' not in event:
                event['rsvp'] = []
            
            user_rsvp = next((r for r in event['rsvp'] if r['user_id'] == username), None)
            
            if user_rsvp:
                event['rsvp'].remove(user_rsvp)
                rsvp_status = None
            else:
                if event.get('max_attendees') and len(event['rsvp']) >= event['max_attendees']:
                    return jsonify({'error': 'Event is full'}), 400
                
                event['rsvp'].append({
                    'user_id': username,
                    'user_name': user['full_name'],
                    'timestamp': datetime.now().isoformat()
                })
                rsvp_status = 'attending'
            
            save_json(EVENT_FILE, events)
            return jsonify({
                'rsvp_status': rsvp_status,
                'attendee_count': len(event['rsvp'])
            })
    
    return jsonify({'error': 'Event not found'}), 404

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

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Simple file serving - in production, use a proper file server
    upload_folder = app.config['UPLOAD_FOLDER']
    for subfolder in ['profiles', 'documents', 'events']:
        file_path = os.path.join(upload_folder, subfolder, filename)
        if os.path.exists(file_path):
            return send_from_directory(os.path.join(upload_folder, subfolder), filename)
    return "File not found", 404

# Messaging System
@app.route('/messages')
def messages():
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    messages = load_json(MESSAGE_FILE)
    user = users[session['username']]
    
    # Get conversations
    user_messages = messages.get('conversations', [])
    conversations = {}
    
    for msg in user_messages:
        if msg['sender_id'] == session['username'] or msg['receiver_id'] == session['username']:
            other_user = msg['receiver_id'] if msg['sender_id'] == session['username'] else msg['sender_id']
            if other_user not in conversations:
                conversations[other_user] = {
                    'user': users.get(other_user, {}),
                    'messages': [],
                    'last_message': None,
                    'unread_count': 0
                }
            conversations[other_user]['messages'].append(msg)
            conversations[other_user]['last_message'] = msg
            if msg['receiver_id'] == session['username'] and not msg['read']:
                conversations[other_user]['unread_count'] += 1
    
    # Sort by last message time
    sorted_conversations = sorted(
        conversations.items(), 
        key=lambda x: x[1]['last_message']['timestamp'], 
        reverse=True
    )
    
    return render_template('messages.html', conversations=sorted_conversations, user=user)

@app.route('/conversation/<other_user_id>')
def conversation(other_user_id):
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    messages = load_json(MESSAGE_FILE)
    
    if other_user_id not in users:
        flash('User not found.')
        return redirect('/messages')
    
    other_user = users[other_user_id]
    current_user = users[session['username']]
    
    # Get conversation messages
    conversation_messages = []
    for msg in messages.get('conversations', []):
        if ((msg['sender_id'] == session['username'] and msg['receiver_id'] == other_user_id) or
            (msg['sender_id'] == other_user_id and msg['receiver_id'] == session['username'])):
            conversation_messages.append(msg)
    
    conversation_messages.sort(key=lambda m: m['timestamp'])
    
    # Mark messages as read
    for msg in conversation_messages:
        if msg['receiver_id'] == session['username']:
            msg['read'] = True
    save_json(MESSAGE_FILE, messages)
    
    return render_template('conversation.html', 
                         messages=conversation_messages, 
                         other_user=other_user,
                         current_user=current_user)

# Prayer Requests and Testimonies
@app.route('/prayers')
def prayers():
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    prayers = load_json(PRAYER_FILE)
    user = users[session['username']]
    
    def is_within_boundary(prayer):
        return (
            prayer['diocese'] == user['diocese'] and
            prayer['denary'] == user['denary'] and
            prayer['parish'] == user['parish'] and
            prayer['local_church'] == user['local_church']
        )
    
    prayer_requests = [p for p in prayers.get('requests', []) if is_within_boundary(p)]
    testimonies = [t for t in prayers.get('testimonies', []) if is_within_boundary(t)]
    
    prayer_requests.sort(key=lambda p: p['timestamp'], reverse=True)
    testimonies.sort(key=lambda t: t['timestamp'], reverse=True)
    
    for item in prayer_requests + testimonies:
        item['time_ago'] = format_timestamp(item['timestamp'])
    
    return render_template('prayers.html', 
                         prayer_requests=prayer_requests, 
                         testimonies=testimonies, 
                         user=user)

@app.route('/add_prayer', methods=['POST'])
def add_prayer():
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    prayers = load_json(PRAYER_FILE)
    user = users[session['username']]
    
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
    
    for prayer in prayers.get('requests', []):
        if prayer['id'] == prayer_id:
            prayer['prayers_count'] = prayer.get('prayers_count', 0) + 1
            save_json(PRAYER_FILE, prayers)
            return jsonify({'prayers_count': prayer['prayers_count']})
    
    return jsonify({'error': 'Prayer request not found'}), 404

# Notifications
@app.route('/notifications')
def notifications():
    if 'username' not in session:
        return redirect('/login')
    
    notifications = load_json(NOTIFICATION_FILE)
    user_notifications = notifications.get(session['username'], [])
    user_notifications.sort(key=lambda n: n['timestamp'], reverse=True)
    
    for notification in user_notifications:
        notification['time_ago'] = format_timestamp(notification['timestamp'])
    
    return render_template('notifications.html', notifications=user_notifications)

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

# File Management
@app.route('/documents')
def documents():
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    user = users[session['username']]
    
    # List uploaded documents
    documents = []
    doc_path = 'uploads/documents'
    if os.path.exists(doc_path):
        for filename in os.listdir(doc_path):
            file_path = os.path.join(doc_path, filename)
            if os.path.isfile(file_path):
                # You might want to store document metadata in JSON
                documents.append({
                    'filename': filename,
                    'size': os.path.getsize(file_path),
                    'uploaded': datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
                })
    
    documents.sort(key=lambda d: d['uploaded'], reverse=True)
    
    return render_template('documents.html', documents=documents, user=user)

@app.route('/upload_document', methods=['POST'])
def upload_document():
    if 'username' not in session:
        return redirect('/login')
    
    users = load_json(USER_FILE)
    user = users[session['username']]
    
    if 'member' in user['rank'].lower():
        flash('Only leaders can upload documents.')
        return redirect('/documents')
    
    if 'document' not in request.files:
        flash('No file selected.')
        return redirect('/documents')
    
    file = request.files['document']
    if file.filename == '':
        flash('No file selected.')
        return redirect('/documents')
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        file_path = os.path.join('uploads/documents', filename)
        file.save(file_path)
        flash('Document uploaded successfully!')
    else:
        flash('Invalid file type.')
    
    return redirect('/documents')

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
    if 'username' not in session:
        return redirect('/login')
    users = load_json(USER_FILE)
    user = users[session['username']]
    if 'chairman' not in user['rank'].lower():
        flash('Only chairmen can view members.')
        return redirect('/dashboard')

    def is_same_area(m):
        return all([
            m['diocese'] == user['diocese'],
            m['denary'] == user['denary'],
            m['parish'] == user['parish'],
            m['local_church'] == user['local_church']
        ])
    members = {u: m for u, m in users.items() if is_same_area(m)}
    return render_template('members.html', members=members, user=user)

@app.route('/reset_password/<target_username>', methods=['POST'])
def reset_password(target_username):
    if 'username' not in session:
        return redirect('/login')
    users = load_json(USER_FILE)
    user = users[session['username']]
    if 'chairman' not in user['rank'].lower():
        return "Access denied", 403
    users[target_username]['password'] = request.form['new_password']
    save_json(USER_FILE, users)
    return redirect('/members')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/login')

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
