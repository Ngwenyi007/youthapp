from flask import Flask, render_template, request, redirect, session, flash
import uuid, json
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
app = Flask(__name__)
app.secret_key = 'youth_secret_key'


USER_FILE = 'users.json'
POST_FILE = 'posts.json'
COMMENT_FILE = 'comments.json'

def load_json(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

def format_timestamp(iso_time):
    delta = datetime.now() - datetime.fromisoformat(iso_time)  # ✅ Fixed this line
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds} seconds ago"
    elif seconds < 3600:
        return f"{seconds // 60} minutes ago"
    elif seconds < 86400:
        return f"{seconds // 3600} hours ago"
    else:
        return f"{seconds // 86400} days ago"

@app.context_processor
def inject_now():
    return {'datetime': datetime}  # ✅ This is okay, now it refers to the correct class

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
            "username": username
        }

        save_json(USER_FILE, users)
        session['username'] = username
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
        post = {
            "id": str(uuid.uuid4()),
            "author": user['full_name'],
            "username": username,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat(),
            "pinned": False,
            "diocese": user['diocese'],
            "denary": user['denary'],
            "parish": user['parish'],
            "local_church": user['local_church']
        }
        posts.insert(0, post)
        save_json(POST_FILE, posts)

    for post in posts:
        if 'timestamp' not in post:
            post['timestamp'] = datetime.now().isoformat()

    visible_posts = [p for p in posts if is_within_boundary(p)]
    visible_posts.sort(key=lambda p: (not p.get('pinned', False), p['timestamp']), reverse=True)

    for p in visible_posts:
        p['time_ago'] = format_timestamp(p['timestamp'])
        p['comments'] = comments.get(p['id'], [])

    return render_template('dashboard.html', user=user, posts=visible_posts)

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
        "timestamp": datetime.datetime.now().isoformat()
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
            "diocese": current_user['diocese']
        }
        users[new_username] = new_user
        save_json(USER_FILE, users)
        flash(f"Added user. Username: {new_username}")
        return redirect('/dashboard')

    return render_template('add_member.html', user=current_user)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
