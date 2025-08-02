from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import json, os, re
from dateutil.relativedelta import relativedelta  # Usisahau hii
import random
import string
from functools import wraps
import uuid
from werkzeug.security import generate_password_hash
import fcntl


app = Flask(__name__)
app.secret_key = "your_secret_key"

USERS_FILE = 'users.json'
POSTS_FILE = 'posts.json'

# 🧠 Automatically adds "organising secretary" to all levels
role_definitions = {
    'Local': ['member', 'chairman', 'secretary', 'organising secretary', 'chaplain', 'matron', 'patron', 'treasurer'],
    'Parish': ['chaplain', 'chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer'],
    'Denary': ['chaplain', 'chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer'],
    'Diocese': ['chaplain', 'chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer'],
    'National': ['chairman', 'secretary', 'organising secretary', 'matron', 'patron', 'treasurer']
}

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
    try:
        with open("posts.json", "r") as f:
            posts = json.load(f)
    except Exception:
        posts = []

    updated = False
    for post in posts:
        if 'id' not in post:
            post['id'] = str(uuid.uuid4())
            updated = True

    if updated:
        with open("posts.json", "w") as f:
            json.dump(posts, f, indent=4)
        print("✅ Missing post IDs assigned and saved.")
    else:
        print("✅ All posts already have IDs.")

fix_missing_post_ids()
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login first.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []  # Return empty list if file is empty or invalid JSON

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
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        code = request.form['code']
        password = request.form['password']

        try:
            with open('users.json', 'r') as f:
                users = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            users = []

        for user in users:
            if user.get('code') == code and user.get('password') == password:
                session['user'] = {
                    'code': user['code'],
                    'fullname': user['fullname'],
                    'rank': user['rank'],
                    'local_church': user['local_church'],
                    'parish': user['parish'],
                    'denary': user['denary'],
                    'diocese': user['diocese']
                }
                session.permanent = True
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

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('login'))

    user = session['user']
    code = user['code']
    fullname = user.get('fullname')
    rank = user.get('rank')
    gender = user.get('gender')
    dob = user.get('dob')
    phone = user.get('phone')
    email = user.get('email')
    local_church = user.get('local_church')
    parish = user.get('parish')
    denary = user.get('denary')
    diocese = user.get('diocese')

    # Filters
    filter_level = request.args.get('filter_level', 'all')
    filter_department = request.args.get('filter_department', 'all')
    search_query = request.args.get('search', '').lower()

    # Load users
    try:
        with open('users.json') as f:
            users = json.load(f)
    except FileNotFoundError:
        users = []

    # Current user full data
    current_user = next((u for u in users if u['code'] == code), None)
    if not current_user:
        flash("User not found.", "error")
        return redirect(url_for('login'))

    # Load posts
    try:
        with open('posts.json') as f:
            all_posts = json.load(f)
    except FileNotFoundError:
        all_posts = []

    # Determine jurisdiction level
    user_level = None
    for level in ['local_church', 'parish', 'denary', 'diocese']:
        if user.get(level):
            user_level = level
            break

    # Filter posts in jurisdiction
    def in_jurisdiction(post):
        return (
            post.get('diocese') == diocese and
            post.get('denary') == denary and
            post.get('parish') == parish and
            post.get('local_church') == local_church
        )

    # Filtering logic
    filtered_posts = []
    for post in all_posts:
        if not in_jurisdiction(post):
            continue
        if filter_level != 'all' and post.get('level') != filter_level:
            continue
        if filter_department != 'all' and post.get('department') != filter_department:
            continue
        if search_query and search_query not in post.get('content', '').lower():
            continue
        filtered_posts.append(post)

    # Sort: pinned posts first, then newest
    filtered_posts.sort(key=lambda x: (not x.get('pinned', False), x.get('timestamp', '')), reverse=True)

    # Members list (for chairman only)
    members = []
    if current_user.get('role') == 'chairman':
        members = [
            u for u in users if
            u.get('diocese') == diocese and
            u.get('denary') == denary and
            u.get('parish') == parish and
            u.get('local_church') == local_church
        ]

    # Member statistics
    total_members = len(members)
    male_members = sum(1 for m in members if m.get('gender') == 'Male')
    female_members = sum(1 for m in members if m.get('gender') == 'Female')

    return render_template(
        'dashboard.html',
        user=user,
        fullname=fullname,
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
       user_rank=user.get('rank'),
       user_code=user.get('code')
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
        data = load_data(USERS_FILE)
        form = request.form

        # Auto-generate unique 5-character code
        existing_codes = {u['code'] for u in data}
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            if code not in existing_codes:
                break

        fullname = form['fullname']
        password = form['password']
        phone = form['phone']
        gender = form['gender']
        age = form['age']
        church_level = form['church_level']
        role = form['role']
        rank = f"{church_level} {role}".lower()
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
        skills = form.get('skills', '')
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
            'fullname': fullname,
            'code': code,
            'password': password,
            'phone': phone,
            'gender': gender,
            'age': age,
            'rank': rank,
            'local_church': local_church,
            'parish': parish,
            'dob': dob,
            'denary': denary,
            'diocese': diocese,
            'residence': residence,
            'education_level': education_level,
            'disability': disability,
            'occupation_status': occupation_status,
            'institution_type': institution_type,
            'talents': talents,
            'skills': skills,
            'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        }

        data.append(user)
        save_data(USERS_FILE, data)
        return redirect(url_for('login'))

    return render_template('register.html')

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
        user['fullname'] = request.form['fullname']
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
            'author': user['fullname'],
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
                'author': user['fullname'],
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

    return render_template('view_my_details.html', user=user_data)
@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')

# ======= Run App =======

if __name__ == '__main__':
    app.run(debug=True)
