from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
os.makedirs('/var/data', exist_ok=True)


import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import json
import os
# Add this import at the top of app.py
from mcq import register_mcq_routes
from flask import Flask
from test import test_bp   # Import the test blueprint (replace with your module name)
from dynamic_db_handler import GOALS
from dynamic_db_handler import GOALS, get_goal_qbank_subjects


  # at top of app.py [file:488]


app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Required for sessions and flashes

# Register the blueprint(s)




# Add this line before if __name__ == '__main__':


# Try this import method first
try:
    from dynamic_db_handler import dynamic_db_handler, register_dynamic_db_routes, find_subject_database, get_all_qbank_subjects
except ImportError:
    from dynamic_db_handler import DynamicDatabaseHandler, register_dynamic_db_routes, find_subject_database, get_all_qbank_subjects
    dynamic_db_handler = DynamicDatabaseHandler()

# CENTRALIZED USER DATABASE CONFIGURATION
USER_DB_FILE = '/var/data/admin_users.db'
DB_FILE = '/var/data/1st_year.db'

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
print("Registered endpoints:")
for rule in app.url_map.iter_rules():
    print(rule.endpoint, "->", rule.rule)


# ✅ REGISTER ROUTES IMMEDIATELY AFTER APP CREATION

# ... rest of your code ...

# --------------------
# CENTRALIZED DATABASE CONNECTION FUNCTIONS
# --------------------
@app.route('/set_goal', methods=['POST'])
def set_goal():
    goal_key = request.form.get('goal')
    if goal_key in GOALS:
        session['current_goal'] = goal_key
        flash(f"Goal set to {GOALS[goal_key]['label']}", 'success')
    else:
        flash("Invalid goal selected", 'error')
    return redirect(url_for('home'))
def get_user_db_connection():
    """ONLY connection function for ALL user operations"""
    conn = sqlite3.connect(USER_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_db_connection():
    """Redirect ALL user operations to centralized database"""
    return get_user_db_connection()

def get_dynamic_subject_connection(subject_name):
    """Keep this ONLY for content (questions) - NOT for users"""
    db_file = find_subject_database(subject_name)
    return dynamic_db_handler.get_connection(db_file)

# --------------------
# CENTRALIZED USER DATABASE SETUP
# --------------------
def create_centralized_user_database():
    """Create admin_users.db as the ONLY user database for the entire system"""
    conn = sqlite3.connect(USER_DB_FILE)
    
    # Main users table - ALL users go here
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            year_of_study TEXT DEFAULT '1st',
            college TEXT,
            user_type TEXT DEFAULT 'student',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Cross-database bookmarks - ALL bookmarks from ALL databases
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            source_database TEXT NOT NULL,  -- Which .db file the question comes from
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, question_id, source_database)
        )
    ''')
    
    # Cross-database notes - ALL user notes from ALL databases
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            source_database TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Cross-database topic completion - ALL completion data
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_topic_completion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            source_database TEXT NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, subject, topic, source_database)
        )
    ''')
    
    # User study analytics - ALL study data centralized
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            questions_viewed INTEGER DEFAULT 0,
            answers_viewed INTEGER DEFAULT 0,
            topics_completed INTEGER DEFAULT 0,
            study_time_minutes INTEGER DEFAULT 0,
            databases_accessed TEXT,  -- JSON array of databases used
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, date)
        )
    ''')
    
    conn.commit()
    conn.close()

def init_db():
    """Initialize centralized user database"""
    create_centralized_user_database()
    print("✅ Centralized admin_users.db initialized successfully!")

# Initialize database when app starts
with app.app_context():
    init_db()

# --------------------
# FREE CONTENT MANAGEMENT FUNCTIONS
# --------------------
def setup_free_content():
    """Mark specific topics as free access - all others require login"""
    # Topics that DON'T require login (free content for everyone)
    free_topics = [
        ('Anatomy', 'Basic Anatomy'),
        ('Anatomy', 'General Anatomy'),
        ('Physiology', 'Basic Physiology'),
        ('Physiology', 'Cardiovascular System'),
        ('Biochemistry', 'Carbohydrates'),
        ('Biochemistry', 'Proteins'),
        ('Pathology', 'General Pathology'),
        ('Pathology', 'Cell Injury'),
        ('Pharmacology', 'General Pharmacology'),
        ('Pharmacology', 'Basic Pharmacokinetics')
    ]
    
    # Apply to all discovered databases
    for category, databases in dynamic_db_handler.discovered_databases.items():
        if category == 'qbank':
            for db_info in databases:
                try:
                    conn = dynamic_db_handler.get_connection(db_info['file'])
                    
                    # First, mark ALL topics as requiring login (premium = 1)
                    conn.execute('UPDATE qbank SET is_premium = 1')
                    
                    # Then mark only specific topics as free (premium = 0)
                    for subject, topic in free_topics:
                        conn.execute('''
                            UPDATE qbank 
                            SET is_premium = 0 
                            WHERE LOWER(subject) = ? AND LOWER(topic) = ?
                        ''', (subject.lower(), topic.lower()))
                    
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"Error setting up content in {db_info['file']}: {e}")
    
    print(f"Content setup completed. {len(free_topics)} topics are free across all databases.")
    return True

def is_topic_login_required(subject, topic):
    """Check if a topic requires user login (returns True if login required)"""
    source_db = find_subject_database(subject)
    try:
        conn = dynamic_db_handler.get_connection(source_db)
        result = conn.execute('''
            SELECT DISTINCT is_premium 
            FROM qbank 
            WHERE LOWER(subject) = ? AND LOWER(topic) = ?
            LIMIT 1
        ''', (subject.lower(), topic.lower())).fetchone()
        conn.close()
        
        # If is_premium = 1, login is required
        # If is_premium = 0, topic is free
        return result and result['is_premium'] == 1
    except Exception as e:
        print(f"Error checking topic access: {e}")
        return True  # Default to requiring login

def mark_topic_as_login_required(subject, topic):
    """Mark a specific topic as requiring login (admin function)"""
    source_db = find_subject_database(subject)
    try:
        conn = dynamic_db_handler.get_connection(source_db)
        conn.execute('''
            UPDATE qbank 
            SET is_premium = 1 
            WHERE LOWER(subject) = ? AND LOWER(topic) = ?
        ''', (subject.lower(), topic.lower()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking topic as login required: {e}")
        return False

def mark_topic_as_free(subject, topic):
    """Mark a specific topic as free access (admin function)"""
    source_db = find_subject_database(subject)
    try:
        conn = dynamic_db_handler.get_connection(source_db)
        conn.execute('''
            UPDATE qbank 
            SET is_premium = 0 
            WHERE LOWER(subject) = ? AND LOWER(topic) = ?
        ''', (subject.lower(), topic.lower()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking topic as free: {e}")
        return False

# --------------------
# USER SESSION MANAGEMENT FUNCTIONS
# --------------------
def ensure_user_session():
    """Validate user session exists and return user_id"""
    if 'user_id' not in session:
        return None
    return session['user_id']

def create_user_session(user_id, username, user_type):
    session['user_id'] = user_id
    session['username'] = username
    session['user_type'] = user_type   # << Important for admin/student role
    session.permanent = True

# --------------------
# CENTRALIZED HELPER FUNCTIONS
# --------------------
def get_question_count(conn, subject_name, topic_name):
    """Get the count of questions for a specific topic"""
    result = conn.execute(
        'SELECT COUNT(*) as count FROM qbank WHERE LOWER(subject) = ? AND topic = ?',
        (subject_name.lower(), topic_name)
    ).fetchone()
    return result['count'] if result else 0

def is_bookmarked(conn_unused, user_id, question_id):
    """Check bookmark in centralized database (ignore conn parameter)"""
    if not user_id:
        return False
    
    user_conn = get_user_db_connection()  # Always admin_users.db
    try:
        result = user_conn.execute(
            'SELECT id FROM user_bookmarks WHERE user_id = ? AND question_id = ?',
            (user_id, question_id)
        ).fetchone()
        return result is not None
    finally:
        user_conn.close()

def is_topic_completed(conn_unused, user_id, subject, topic):
    """Check completion in centralized database"""
    if not user_id:
        return False
    
    source_db = find_subject_database(subject)
    user_conn = get_user_db_connection()  # Always admin_users.db
    try:
        result = user_conn.execute(
            '''SELECT id FROM user_topic_completion 
               WHERE user_id = ? AND LOWER(subject) = ? AND topic = ? AND source_database = ?''',
            (user_id, subject.lower(), topic, source_db)
        ).fetchone()
        return result is not None
    finally:
        user_conn.close()

def get_user_note(conn_unused, user_id, question_id):
    """Get note from centralized database"""
    if not user_id:
        return None
    
    user_conn = get_user_db_connection()  # Always admin_users.db
    try:
        result = user_conn.execute(
            'SELECT note FROM user_notes WHERE user_id = ? AND question_id = ?',
            (user_id, question_id)
        ).fetchone()
        return result['note'] if result else None
    finally:
        user_conn.close()

def get_next_topic(conn, subject_name, current_topic):
    """Get next topic sorted by CHAPTER first, then topic name"""
    topics = conn.execute(
        '''
        SELECT DISTINCT topic 
        FROM qbank 
        WHERE LOWER(subject) = ? AND topic != "" AND topic != "None"
        ORDER BY chapter ASC, topic ASC
        ''',
        (subject_name.lower(),)
    ).fetchall()
    
    topic_list = [t['topic'] for t in topics]
    try:
        current_index = topic_list.index(current_topic)
        if current_index < len(topic_list) - 1:
            return topic_list[current_index + 1]
    except ValueError:
        pass
    return None
# CENTRALIZED DATABASE OPERATIONS
# --------------------
def add_bookmark_to_db(user_id, question_id, subject, topic):
    """ALL bookmarks go to admin_users.db regardless of source"""
    source_db = find_subject_database(subject)
    
    conn = get_user_db_connection()  # Always admin_users.db
    try:
        conn.execute('''
            INSERT INTO user_bookmarks 
            (user_id, question_id, subject, topic, source_database) 
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, question_id, subject, topic, source_db))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def remove_bookmark_from_db(user_id, question_id):
    """Remove bookmark from centralized database"""
    conn = get_user_db_connection()  # Always admin_users.db
    try:
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM user_bookmarks WHERE user_id = ? AND question_id = ?',
            (user_id, question_id)
        )
        success = cursor.rowcount > 0
        conn.commit()
        return success
    except Exception as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

# --------------------
# BOOKMARK ROUTES
# --------------------
@app.route('/toggle_bookmark', methods=['POST'])
def toggle_bookmark():
    """Main bookmark toggle endpoint"""
    user_id = ensure_user_session()
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login to bookmark questions'})
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received'})
        
        question_id = data.get('question_id')
        subject = data.get('subject')
        topic = data.get('topic')
        
        if not all([question_id, subject, topic]):
            return jsonify({'success': False, 'message': 'Missing required data'})
        
        # Check if bookmark already exists in centralized database
        conn = get_user_db_connection()
        existing = conn.execute(
            'SELECT id FROM user_bookmarks WHERE user_id = ? AND question_id = ?',
            (user_id, question_id)
        ).fetchone()
        conn.close()
        
        if existing:
            success = remove_bookmark_from_db(user_id, question_id)
            if success:
                return jsonify({
                    'success': True, 
                    'bookmarked': False, 
                    'message': 'Bookmark removed successfully'
                })
            else:
                return jsonify({'success': False, 'message': 'Failed to remove bookmark'})
        else:
            success = add_bookmark_to_db(user_id, question_id, subject, topic)
            if success:
                return jsonify({
                    'success': True, 
                    'bookmarked': True, 
                    'message': 'Bookmark added successfully'
                })
            else:
                return jsonify({'success': False, 'message': 'Bookmark already exists or failed to add'})
                
    except Exception as e:
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})

@app.route('/add_bookmark', methods=['POST'])
def add_bookmark():
    """Alternative route for adding bookmarks via form submission"""
    user_id = ensure_user_session()
    if not user_id:
        flash('Please login to bookmark questions')
        return redirect(url_for('login'))
    
    question_id = request.form.get('question_id')
    subject = request.form.get('subject')
    topic = request.form.get('topic')
    
    if not all([question_id, subject, topic]):
        flash('Missing required bookmark data')
        return redirect(request.referrer or url_for('home'))
    
    success = add_bookmark_to_db(user_id, int(question_id), subject, topic)
    
    if success:
        flash('Question bookmarked successfully!')
    else:
        flash('Question is already bookmarked or error occurred')
    
    return redirect(request.referrer or url_for('home'))

@app.route('/bookmarks')
def bookmarks():
    """Get ALL bookmarks from centralized database"""
    user_id = ensure_user_session()
    if not user_id:
        flash('Please login to view your bookmarks')
        return redirect(url_for('login'))
    
    user_conn = get_user_db_connection()  # Always admin_users.db
    try:
        # Get bookmarks with source database info
        bookmarks = user_conn.execute('''
            SELECT * FROM user_bookmarks 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        ''', (user_id,)).fetchall()
        
        # Enrich with actual question data from source databases
        enriched_bookmarks = []
        for bookmark in bookmarks:
            try:
                source_conn = dynamic_db_handler.get_connection(bookmark['source_database'])
                question = source_conn.execute(
                    'SELECT question, answer FROM qbank WHERE id = ?',
                    (bookmark['question_id'],)
                ).fetchone()
                
                if question:
                    enriched_bookmarks.append({
                        'bookmark_id': bookmark['id'],
                        'question_id': bookmark['question_id'],
                        'subject': bookmark['subject'],
                        'topic': bookmark['topic'],
                        'source_database': bookmark['source_database'],
                        'created_at': bookmark['created_at'],
                        'question': question['question'],
                        'answer': question['answer']
                    })
                source_conn.close()
            except Exception as e:
                print(f"Error enriching bookmark from {bookmark['source_database']}: {e}")
        
        return render_template('bookmarks.html', bookmarks=enriched_bookmarks)
    finally:
        user_conn.close()

@app.route('/bookmarks/subject/<subject_name>')
def bookmarks_by_subject(subject_name):
    """Filter bookmarks by subject - Requires login"""
    user_id = ensure_user_session()
    if not user_id:
        flash('Please login first')
        return redirect(url_for('login'))
    
    user_conn = get_user_db_connection()
    try:
        bookmarks = user_conn.execute('''
            SELECT * FROM user_bookmarks 
            WHERE user_id = ? AND LOWER(subject) = ?
            ORDER BY created_at DESC
        ''', (user_id, subject_name.lower())).fetchall()
        
        # Enrich bookmarks with actual question data
        enriched_bookmarks = []
        for bookmark in bookmarks:
            try:
                source_conn = dynamic_db_handler.get_connection(bookmark['source_database'])
                question = source_conn.execute(
                    'SELECT question, answer FROM qbank WHERE id = ?',
                    (bookmark['question_id'],)
                ).fetchone()
                
                if question:
                    enriched_bookmarks.append({
                        'bookmark_id': bookmark['id'],
                        'question_id': bookmark['question_id'],
                        'subject': bookmark['subject'],
                        'topic': bookmark['topic'],
                        'source_database': bookmark['source_database'],
                        'created_at': bookmark['created_at'],
                        'question': question['question'],
                        'answer': question['answer']
                    })
                source_conn.close()
            except Exception as e:
                print(f"Error enriching bookmark: {e}")
        
        return render_template('bookmarks.html', 
                             bookmarks=enriched_bookmarks, 
                             filtered_subject=subject_name)
    finally:
        user_conn.close()

@app.route('/remove_bookmark/<int:bookmark_id>', methods=['POST'])
def remove_bookmark_by_id(bookmark_id):
    """Remove a specific bookmark by bookmark ID"""
    user_id = ensure_user_session()
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login first'})
    
    conn = get_user_db_connection()
    try:
        # Verify bookmark belongs to user and get question_id
        bookmark = conn.execute(
            'SELECT question_id FROM user_bookmarks WHERE id = ? AND user_id = ?',
            (bookmark_id, user_id)
        ).fetchone()
        
        if not bookmark:
            return jsonify({'success': False, 'message': 'Bookmark not found'})
        
        # Remove bookmark using existing function
        success = remove_bookmark_from_db(user_id, bookmark['question_id'])
        
        if success:
            return jsonify({'success': True, 'message': 'Bookmark removed successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to remove bookmark'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        conn.close()

# --------------------
# ADMIN ROUTES
# --------------------
@app.route('/admin/setup_content_access')
def admin_setup_content_access():
    """Admin route to setup content access - Only specific topics are free"""
    success = setup_free_content()
    if success:
        return "Content access setup completed. Only specific basic topics are free, all others require login. <a href='/home'>Back to Home</a>"
    else:
        return "Failed to setup content access. <a href='/home'>Back to Home</a>"

@app.route('/admin/require_login/<subject>/<topic>')
def admin_require_login(subject, topic):
    """Admin route to mark specific topic as requiring login"""
    success = mark_topic_as_login_required(subject, topic)
    if success:
        return f"Topic '{topic}' in '{subject}' now requires login. <a href='/home'>Back to Home</a>"
    else:
        return f"Failed to update topic access. <a href='/home'>Back to Home</a>"

@app.route('/admin/make_free/<subject>/<topic>')
def admin_make_free(subject, topic):
    """Admin route to mark specific topic as free access"""
    success = mark_topic_as_free(subject, topic)
    if success:
        return f"Topic '{topic}' in '{subject}' is now free for everyone. <a href='/home'>Back to Home</a>"
    else:
        return f"Failed to update topic access. <a href='/home'>Back to Home</a>"

# --------------------
# CENTRALIZED TOPIC COMPLETION & NOTES
# --------------------
@app.route('/complete_topic', methods=['POST'])
def complete_topic():
    user_id = ensure_user_session()
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login to track progress'})
    
    try:
        data = request.get_json()
        subject = data.get('subject')
        topic = data.get('topic')
        source_db = find_subject_database(subject)
        
        conn = get_user_db_connection()  # Always admin_users.db
        
        # Check if already completed
        existing = conn.execute('''
            SELECT id FROM user_topic_completion 
            WHERE user_id = ? AND LOWER(subject) = ? AND topic = ? AND source_database = ?
        ''', (user_id, subject.lower(), topic, source_db)).fetchone()
        
        if not existing:
            conn.execute('''
                INSERT INTO user_topic_completion 
                (user_id, subject, topic, source_database) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, subject, topic, source_db))
            conn.commit()
        
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/save_note', methods=['POST'])
def save_note():
    user_id = ensure_user_session()
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login to save notes'})
    
    try:
        data = request.get_json()
        question_id = data.get('question_id')
        note = data.get('note', '').strip()
        subject = data.get('subject', '')
        source_db = find_subject_database(subject)
        
        conn = get_user_db_connection()  # Always admin_users.db
        
        if note:
            conn.execute('''
                INSERT OR REPLACE INTO user_notes 
                (user_id, question_id, note, source_database, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, question_id, note, source_db))
        else:
            conn.execute(
                'DELETE FROM user_notes WHERE user_id = ? AND question_id = ?',
                (user_id, question_id)
            )
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# --------------------
# AUTHENTICATION ROUTES
# --------------------
@app.route('/')
def landing():
    return render_template('index.html', goals=GOALS)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # Check if user came from login-required content redirect
    from_restricted = request.args.get('restricted', False)
    
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']

        if not username or not email or not password:
            flash('Please fill all the fields.')
            return redirect(url_for('signup'))

        conn = get_user_db_connection()  # Always admin_users.db
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user:
            conn.close()
            flash('Email already registered.')
            return redirect(url_for('signup'))

        hashed_pw = generate_password_hash(password)
        conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                     (username, email, hashed_pw))
        conn.commit()
        conn.close()
        flash('Account created! Please login.')
        return redirect(url_for('login'))

    return render_template('signup.html', from_restricted=from_restricted)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['username'].strip().lower()
        password = request.form['password']

        conn = get_user_db_connection()  # Always admin_users.db
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            # Update last login
            user_conn = get_user_db_connection()
            user_conn.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user['id'],)
            )
            user_conn.commit()
            user_conn.close()
            
            # If user is admin, optionally redirect to admin login route
            if user['user_type'] == 'admin':
                flash('Admins must login via the admin login page.')
                return redirect(url_for('admin_login'))

            # Pass user_type to session in create_user_session
            create_user_session(user['id'], user['username'], user['user_type'])

            flash(f'Welcome back, {user["username"]}!')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials.')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['username'].strip().lower()
        password = request.form['password']

        conn = get_user_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password) and user['user_type'] == 'admin':
            create_user_session(user['id'], user['username'], 'admin')
            flash(f'Welcome Admin {user["username"]}!', 'success')
            return redirect(url_for('admin_dashboard'))  # your admin dashboard or panel
        else:
            flash('Invalid admin credentials.', 'danger')
            return redirect(url_for('admin_login'))

    return render_template('admin_home.html')



@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('landing'))



@app.route('/admin/debug_users')
def debug_users():
    """Debug route to check user data - FIXED for missing columns"""
    try:
        # Check 1st_year.db users
        old_conn = sqlite3.connect('/var/data/1st_year.db')
        old_conn.row_factory = sqlite3.Row
        
        # Check if users table exists
        tables = old_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        old_table_names = [t['name'] for t in tables]
        
        if 'users' in old_table_names:
            # Check which columns exist in users table
            schema = old_conn.execute("PRAGMA table_info(users)").fetchall()
            column_names = [col[1] for col in schema]
            
            # Build SELECT query based on available columns
            if 'created_at' in column_names:
                old_users = old_conn.execute('SELECT id, username, email, created_at FROM users').fetchall()
            else:
                old_users = old_conn.execute('SELECT id, username, email FROM users').fetchall()
            
            old_count = len(old_users)
        else:
            old_users = []
            old_count = 0
            column_names = []
        
        old_conn.close()
        
        # Check admin_users.db users
        new_conn = get_user_db_connection()
        new_users = new_conn.execute('SELECT id, username, email, created_at FROM users').fetchall()
        new_count = len(new_users)
        new_conn.close()
        
        result = f"""
        <h2>🔍 User Database Debug Information</h2>
        
        <h3>📊 1st_year.db (Old Database)</h3>
        <p><strong>Tables found:</strong> {', '.join(old_table_names)}</p>
        <p><strong>Available columns in users table:</strong> {', '.join(column_names) if column_names else 'N/A'}</p>
        <p><strong>Users count:</strong> {old_count}</p>
        
        {'<h4>Old Users:</h4><ul>' + ''.join([f'<li>ID: {u["id"]}, Username: {u["username"]}, Email: {u["email"]}' + (f', Created: {u["created_at"]}' if "created_at" in u.keys() else '') + '</li>' for u in old_users[:5]]) + '</ul>' if old_users else '<p>No users found in old database</p>'}
        
        <h3>📊 admin_users.db (New Centralized Database)</h3>
        <p><strong>Users count:</strong> {new_count}</p>
        
        {'<h4>New Users:</h4><ul>' + ''.join([f'<li>ID: {u["id"]}, Username: {u["username"]}, Email: {u["email"]}, Created: {u["created_at"]}</li>' for u in new_users[:5]]) + '</ul>' if new_users else '<p>No users found in new database</p>'}
        
        <div style="margin-top: 20px; padding: 15px; background: #e7f3ff; border-radius: 4px;">
        <strong>💡 Migration Status:</strong>
        <ul>
            <li>Old database columns: {', '.join(column_names) if column_names else 'No users table'}</li>
            <li>Missing created_at column: {'❌ Yes' if 'created_at' not in column_names else '✅ No'}</li>
            <li>Ready for migration: {'✅ Yes' if old_users else '❌ No users to migrate'}</li>
        </ul>
        </div>
        
        <p><a href="/admin/dynamic_db_manager">Back to Database Manager</a></p>
        <p><a href="/admin/migrate_users_manual">Run Fixed Migration</a></p>
        """
        
        return result
        
    except Exception as e:
        return f"<h2>❌ Debug Error:</h2><p>{str(e)}</p><p><a href='/admin/dynamic_db_manager'>Back</a></p>"
    
@app.route('/admin/migrate_users_with_passwords')
def migrate_users_with_passwords():
    """Migrate users while preserving password hashes correctly"""
    try:
        # Get users from old database
        old_conn = sqlite3.connect('/var/data/1st_year.db')
        old_conn.row_factory = sqlite3.Row
        
        users = old_conn.execute('SELECT id, username, email, password FROM users').fetchall()
        old_conn.close()
        
        if not users:
            return "No users found to migrate. <a href='/admin/dynamic_db_manager'>Back</a>"
        
        new_conn = get_user_db_connection()
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        migration_details = []
        
        for user in users:
            try:
                # Check if user already exists by email
                existing = new_conn.execute('SELECT id FROM users WHERE email = ?', (user['email'],)).fetchone()
                
                if existing:
                    migration_details.append(f"SKIPPED: {user['email']} (already exists)")
                    skipped_count += 1
                else:
                    # Migrate user with existing password hash (don't re-encrypt)
                    new_conn.execute('''
                        INSERT INTO users (username, email, password, created_at)
                        VALUES (?, ?, ?, ?)
                    ''', (user['username'], user['email'], user['password'], datetime.datetime.now().isoformat()))
                    
                    migration_details.append(f"✅ MIGRATED: {user['email']} (ID: {user['id']})")
                    migrated_count += 1
                
            except Exception as e:
                migration_details.append(f"❌ ERROR: {user['email']} - {str(e)}")
                error_count += 1
        
        new_conn.commit()
        new_conn.close()
        
        return f"""
        <h2>✅ Password-Aware Migration Completed!</h2>
        
        <div style="background: #d4edda; padding: 15px; border-radius: 4px; margin: 10px 0;">
        <h3>📊 Migration Summary:</h3>
        <ul>
            <li><strong>Users migrated:</strong> {migrated_count}</li>
            <li><strong>Users skipped (already exist):</strong> {skipped_count}</li>
            <li><strong>Errors:</strong> {error_count}</li>
        </ul>
        </div>
        
        <div style="background: #f8f9fa; padding: 15px; border-radius: 4px; margin: 10px 0;">
        <h3>📝 Detailed Log:</h3>
        <ul>
        {''.join([f'<li>{detail}</li>' for detail in migration_details])}
        </ul>
        </div>
        
        <div style="background: #e7f3ff; padding: 15px; border-radius: 4px; margin: 10px 0;">
        <h3>🔐 Password Migration Notes:</h3>
        <ul>
            <li>Existing password hashes are preserved (not re-encrypted)</li>
            <li>Users should be able to login with their original passwords</li>
            <li>If login fails, users may need to reset passwords</li>
        </ul>
        </div>
        
        <p><a href="/admin/edit_table/admin_users.db/users">View Migrated Users</a></p>
        <p><a href="/admin/debug_users">Check Debug Status</a></p>
        <p><a href="/admin/dynamic_db_manager">Back to Database Manager</a></p>
        """
        
    except Exception as e:
        return f"<h2>❌ Migration Error:</h2><p>{str(e)}</p><p><a href='/admin/dynamic_db_manager'>Back</a></p>"


@app.route('/admin/force_migrate_users')
def force_migrate_users():
    """Force migrate users with detailed logging"""
    try:
        old_conn = sqlite3.connect('/var/data/1st_year.db')
        old_conn.row_factory = sqlite3.Row
        
        users = old_conn.execute('SELECT id, username, email, password FROM users').fetchall()
        old_conn.close()
        
        new_conn = get_user_db_connection()
        
        migration_log = []
        
        for user in users:
            try:
                # Check if user already exists
                existing = new_conn.execute('SELECT id FROM users WHERE email = ?', (user['email'],)).fetchone()
                
                if existing:
                    migration_log.append(f"SKIPPED: {user['email']} (already exists)")
                else:
                    new_conn.execute('''
                        INSERT INTO users (username, email, password, created_at)
                        VALUES (?, ?, ?, ?)
                    ''', (user['username'], user['email'], user['password'], datetime.datetime.now().isoformat()))
                    migration_log.append(f"MIGRATED: {user['email']}")
                
            except Exception as e:
                migration_log.append(f"ERROR: {user['email']} - {str(e)}")
        
        new_conn.commit()
        new_conn.close()
        
        return f"""
        <h2>🔍 Force Migration Results</h2>
        <ul>
        {''.join([f'<li>{log}</li>' for log in migration_log])}
        </ul>
        <p><a href="/admin/debug_users">Check Debug Status</a></p>
        """
        
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/admin/migrate_users_manual')
def migrate_users_manual():
    """Manual migration trigger for existing users - FIXED for missing columns"""
    try:
        # Check if admin_users.db exists
        if not os.path.exists(USER_DB_FILE):
            create_centralized_user_database()
            print("✅ Created admin_users.db")
        
        # Get existing users from 1st_year.db
        old_conn = sqlite3.connect('/var/data/1st_year.db')
        old_conn.row_factory = sqlite3.Row
        
        # Check if users table exists in old database
        tables = old_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t['name'] for t in tables]
        
        if 'users' not in table_names:
            old_conn.close()
            return "No users found in 1st_year.db to migrate. <a href='/admin/dynamic_db_manager'>Back</a>"
        
        # Get table schema to check which columns exist
        schema = old_conn.execute("PRAGMA table_info(users)").fetchall()
        column_names = [col[1] for col in schema]
        
        # Get users with flexible column selection
        if 'created_at' in column_names:
            users = old_conn.execute('SELECT * FROM users').fetchall()
        else:
            users = old_conn.execute('SELECT id, username, email, password FROM users').fetchall()
        
        # Get other data if tables exist
        bookmarks = []
        notes = []
        completions = []
        
        if 'bookmarks' in table_names:
            bookmarks_schema = old_conn.execute("PRAGMA table_info(bookmarks)").fetchall()
            bookmarks_columns = [col[1] for col in bookmarks_schema]
            if 'created_at' in bookmarks_columns:
                bookmarks = old_conn.execute('SELECT * FROM bookmarks').fetchall()
            else:
                bookmarks = old_conn.execute('SELECT user_id, question_id, subject, topic FROM bookmarks').fetchall()
        
        if 'user_notes' in table_names:
            notes = old_conn.execute('SELECT * FROM user_notes').fetchall()
        if 'topic_completion' in table_names:
            completions = old_conn.execute('SELECT * FROM topic_completion').fetchall()
        
        old_conn.close()
        
        # Insert into centralized database
        new_conn = get_user_db_connection()
        
        migrated_users = 0
        migrated_bookmarks = 0
        migrated_notes = 0
        migrated_completions = 0
        
        # Migrate users with flexible created_at handling
        for user in users:
            try:
                created_at = user.get('created_at', datetime.datetime.now().isoformat())
                new_conn.execute('''
                    INSERT OR IGNORE INTO users 
                    (username, email, password, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (user['username'], user['email'], user['password'], created_at))
                migrated_users += 1
            except Exception as e:
                print(f"Error migrating user {user['email']}: {e}")
        
        # Migrate bookmarks with flexible created_at handling
        for bookmark in bookmarks:
            try:
                created_at = bookmark.get('created_at', datetime.datetime.now().isoformat())
                new_conn.execute('''
                    INSERT OR IGNORE INTO user_bookmarks 
                    (user_id, question_id, subject, topic, source_database, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (bookmark['user_id'], bookmark['question_id'], 
                      bookmark['subject'], bookmark['topic'], '1st_year.db', created_at))
                migrated_bookmarks += 1
            except Exception as e:
                print(f"Error migrating bookmark: {e}")
        
        # Migrate notes (if they exist)
        for note in notes:
            try:
                created_at = note.get('created_at', datetime.datetime.now().isoformat())
                updated_at = note.get('updated_at', created_at)
                new_conn.execute('''
                    INSERT OR IGNORE INTO user_notes 
                    (user_id, question_id, note, source_database, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (note['user_id'], note['question_id'], note['note'], 
                      '1st_year.db', created_at, updated_at))
                migrated_notes += 1
            except Exception as e:
                print(f"Error migrating note: {e}")
        
        # Migrate topic completions
        for completion in completions:
            try:
                completed_at = completion.get('completed_at', datetime.datetime.now().isoformat())
                new_conn.execute('''
                    INSERT OR IGNORE INTO user_topic_completion 
                    (user_id, subject, topic, source_database, completed_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (completion['user_id'], completion['subject'], completion['topic'], 
                      '1st_year.db', completed_at))
                migrated_completions += 1
            except Exception as e:
                print(f"Error migrating completion: {e}")
        
        new_conn.commit()
        new_conn.close()
        
        return f"""
        <h2>✅ Migration Completed Successfully!</h2>
        <ul>
            <li><strong>Users migrated:</strong> {migrated_users}</li>
            <li><strong>Bookmarks migrated:</strong> {migrated_bookmarks}</li>
            <li><strong>Notes migrated:</strong> {migrated_notes}</li>
            <li><strong>Topic completions migrated:</strong> {migrated_completions}</li>
        </ul>
        <p><a href="/admin/dynamic_db_manager">Back to Database Manager</a></p>
        <p><a href="/admin/edit_table/admin_users.db/users">View Migrated Users</a></p>
        """
        
    except Exception as e:
        return f"<h2>❌ Migration Error:</h2><p>{str(e)}</p><p><a href='/admin/dynamic_db_manager'>Back</a></p>"

# --------------------
# MAIN APPLICATION ROUTES
# --------------------
@app.route('/home')
def home():

    """UPDATED: Home page - Uses dynamic database discovery"""
    user_id = session.get('user_id')

    goal_key = session.get('current_goal')


    # Get subjects from all databases dynamically
    try:
        all_subjects = get_goal_qbank_subjects(goal_key)
        print(f"Found subjects for goal {goal_key}: {list(all_subjects.keys())}")
    except Exception as e:
        print(f"Error getting goal-specific subjects, falling back to single database: {e}")


        # Fallback to original logic if dynamic fails
        conn = get_dynamic_subject_connection('Anatomy')  # Use any subject for fallback
        rows = conn.execute('SELECT DISTINCT subject FROM qbank ORDER BY subject').fetchall()
        db_subjects = {row['subject'].strip().lower() for row in rows if row['subject']}
        all_subjects = {s.title(): [{'database': find_subject_database(s), 'question_count': 0}] for s in db_subjects}
        conn.close()

    # Hardcoded MBBS Subject to Prof Year Mapping
    PROF_YEAR_MAP = {
        "1st Prof": ["Anatomy", "Physiology", "Biochemistry"],
        "2nd Prof": ["Pathology", "Microbiology", "Pharmacology", "Forensic Medicine"],
        "3rd Prof Part 1": ["Community Medicine", "ENT", "Ophthalmology"],
        "3rd Prof Part 2": ["Medicine", "Surgery", "Pediatrics", "Obstetrics & Gynecology", 
                            "Orthopedics", "Dermatology", "Psychiatry", "Radiology"]
    }

    grouped_subjects = {}

    # Categorize subjects found in databases
    for year, subjects in PROF_YEAR_MAP.items():
        matched_subjects = []
        for subject in subjects:
            if subject in all_subjects:
                # Use the first database that has this subject
                db_info = all_subjects[subject][0]
                
                # Get completion status for this subject (only for logged-in users)
                completed_topics = 0
                total_topics = 0
                if user_id:
                    try:
                        conn = dynamic_db_handler.get_connection(db_info['database'])
                        total_topics_result = conn.execute(
                            'SELECT COUNT(DISTINCT topic) as count FROM qbank WHERE LOWER(subject) = ?',
                            (subject.lower(),)
                        ).fetchone()
                        total_topics = total_topics_result['count'] if total_topics_result else 0
                        
                        # Get completion from centralized database
                        user_conn = get_user_db_connection()
                        completed_topics_result = user_conn.execute(
                            'SELECT COUNT(*) as count FROM user_topic_completion WHERE user_id = ? AND LOWER(subject) = ? AND source_database = ?',
                            (user_id, subject.lower(), db_info['database'])
                        ).fetchone()
                        completed_topics = completed_topics_result['count'] if completed_topics_result else 0
                        user_conn.close()
                        conn.close()
                    except Exception as e:
                        print(f"Error getting completion for {subject}: {e}")
                
                matched_subjects.append({
                    'name': subject,
                    'completed_topics': completed_topics,
                    'total_topics': total_topics
                })
        
        if matched_subjects:
            grouped_subjects[year] = matched_subjects

    # Fallback: if nothing matched, show all subjects found
    if not grouped_subjects:
        grouped_subjects["Available Subjects"] = []
        for subject, db_list in all_subjects.items():
            grouped_subjects["Available Subjects"].append({
                'name': subject.title(),
                'completed_topics': 0,
                'total_topics': 0
            })

    return render_template('home.html', grouped_subjects=grouped_subjects, current_goal=goal_key)


@app.route('/subject/<subject_name>')
def show_subject(subject_name):
    """UPDATED: Subject page - Uses dynamic database detection"""
    user_id = session.get('user_id')

    # Dynamic database selection
    try:
        conn = get_dynamic_subject_connection(subject_name)
        print(f"Using dynamic database for {subject_name}")  # Debug line
    except Exception as e:
        print(f"Error with dynamic connection, falling back to default: {e}")
        conn = get_dynamic_subject_connection('Anatomy')  # Fallback

    # Rest of your existing code stays exactly the same!
    chapters = conn.execute(
        '''
        SELECT DISTINCT chapter 
        FROM qbank 
        WHERE LOWER(subject) = ? AND chapter != "" 
        ORDER BY chapter
        ''',
        (subject_name.lower(),)
    ).fetchall()

    # For each chapter, get the topics with question counts
    chapters_with_topics = []
    for row in chapters:
        chapter = row['chapter']
        topics = conn.execute(
            '''
            SELECT DISTINCT topic 
            FROM qbank 
            WHERE LOWER(subject) = ? AND chapter = ? AND topic != "" 
            ORDER BY topic
            ''',
            (subject_name.lower(), chapter)
        ).fetchall()
        
        # Enhanced topic list with question counts and access information
        enhanced_topics = []
        for topic_row in topics:
            topic_name = topic_row['topic']
            question_count = get_question_count(conn, subject_name, topic_name)
            is_completed = is_topic_completed(conn, user_id, subject_name, topic_name)
            
            # Check if topic requires login (FIXED: Only show lock if user is NOT logged in)
            topic_requires_login = is_topic_login_required(subject_name, topic_name)
            show_lock = topic_requires_login and not user_id  # Only show lock if login required AND user not logged in
            
            # Generate a rating based on question count
            if question_count >= 50:
                rating = 4.8
            elif question_count >= 30:
                rating = 4.5
            elif question_count >= 15:
                rating = 4.2
            elif question_count >= 5:
                rating = 4.0
            else:
                rating = 3.8
            
            # Determine status - show login required only if user not logged in
            if show_lock:
                status = 'LOGIN REQUIRED'
            else:
                status = 'FREE'
            
            topic_data = {
                'name': topic_name,
                'question_count': question_count,
                'rating': rating,
                'status': status,
                'completed': is_completed,
                'requires_login': show_lock  # This controls the lock icon
            }
            enhanced_topics.append(topic_data)
        
        chapters_with_topics.append({
            'chapter': chapter, 
            'topics': enhanced_topics
        })

    conn.close()
    return render_template('subject_chapters.html',
                           subject=subject_name.title(),
                           chapters=chapters_with_topics)

@app.route('/subject/<subject_name>/topic/<topic_name>')
def show_topic(subject_name, topic_name):
    """Topic route - CORRECTED: Most topics require login, only specific ones are free"""
    
    # Check if this specific topic requires login (CORRECTED LOGIC)
    if is_topic_login_required(subject_name, topic_name):
        user_id = ensure_user_session()
        if not user_id:
            flash('🔒 This topic requires login to access. Please sign up or log in to continue your medical studies.', 'info')
            return redirect(url_for('signup', restricted=True))
    
    # Topic is accessible - proceed to show content
    try:
        conn = get_dynamic_subject_connection(subject_name)
    except Exception as e:
        print(f"Error with dynamic connection, falling back to default: {e}")
        conn = get_dynamic_subject_connection('Anatomy')
    
    row = conn.execute(
        'SELECT id FROM qbank WHERE LOWER(subject)=? AND topic=? ORDER BY id LIMIT 1',
        (subject_name.lower(), topic_name)
    ).fetchone()
    conn.close()

    if row:
        return redirect(url_for(
            'show_question',
            subject_name=subject_name,
            topic_name=topic_name,
            qid=row['id']
        ))
    return "<h2>No questions found for this topic</h2>"

@app.route('/subject/<subject_name>/topic/<topic_name>/question/<int:qid>')
def show_question(subject_name, topic_name, qid):
    """UPDATED: Question route - Uses dynamic database"""
    
    # Check if this topic requires login
    if is_topic_login_required(subject_name, topic_name):
        user_id = ensure_user_session()
        if not user_id:
            flash('🔒 This content requires login. Please sign up or log in to continue.', 'info')
            return redirect(url_for('signup', restricted=True))
    
    # Dynamic database connection
    try:
        conn = get_dynamic_subject_connection(subject_name)
    except Exception as e:
        print(f"Error with dynamic connection, falling back to default: {e}")
        conn = get_dynamic_subject_connection('Anatomy')
    
    user_id = session.get('user_id')

    # Get all question ids for pagination
    all_ids = conn.execute(
        'SELECT id FROM qbank WHERE LOWER(subject)=? AND topic=? ORDER BY id',
        (subject_name.lower(), topic_name)
    ).fetchall()
    id_list = [r['id'] for r in all_ids]

    try:
        index = id_list.index(qid)
    except ValueError:
        conn.close()
        return "<h2>Question not found</h2>"

    prev_qid = id_list[index-1] if index > 0 else None
    next_qid = id_list[index+1] if index < len(id_list)-1 else None
    is_last_question = index == len(id_list) - 1

    question = conn.execute('SELECT * FROM qbank WHERE id=?', (qid,)).fetchone()
    bookmarked = is_bookmarked(conn, user_id, qid)
    
    # Get next topic for navigation
    next_topic = get_next_topic(conn, subject_name, topic_name) if is_last_question else None
    
    conn.close()

    return render_template(
        'question.html',
        subject=subject_name,
        topic=topic_name,
        q=question,
        current_index=index + 1,
        total=len(id_list),
        prev_qid=prev_qid,
        next_qid=next_qid,
        is_last_question=is_last_question,
        next_topic=next_topic,
        bookmarked=bookmarked
    )


@app.route('/subscribe', methods=['POST'])
def subscribe():
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']
    name = request.form.get('name', '').strip()
    goal = request.form.get('goal')

    if not name or not goal:
        flash("Name and goal are required.", "error")
        return redirect(url_for('home'))

    conn = sqlite3.connect('/var/data/admin_users.db')
    conn.row_factory = sqlite3.Row
    try:
        # Optional: update name if you want to sync it
        conn.execute(
            "UPDATE users SET username = ?, subscription_status = ?, subscription_goal = ? WHERE id = ?",
            (name, 'subscribed', goal, user_id)
        )
        conn.commit()
        flash(f"Subscribed to {goal}!", "success")
    finally:
        conn.close()

    # Also keep in session for quick access
    session['subscription_status'] = 'subscribed'
    session['subscription_goal'] = goal

    return redirect(url_for('home'))
@app.route('/subject/<subject_name>/topic/<topic_name>/answer/<int:qid>')
def show_answer(subject_name, topic_name, qid):
    """UPDATED: Answer route - Uses dynamic database"""
    
    # Check if this topic requires login
    if is_topic_login_required(subject_name, topic_name):
        user_id = ensure_user_session()
        if not user_id:
            flash('🔒 This content requires login. Please sign up or log in to access detailed answers.', 'info')
            return redirect(url_for('signup', restricted=True))
    
    # Dynamic database connection
    try:
        conn = get_dynamic_subject_connection(subject_name)
    except Exception as e:
        print(f"Error with dynamic connection, falling back to default: {e}")
        conn = get_dynamic_subject_connection('Anatomy')
    
    user_id = session.get('user_id')
    
    all_ids = conn.execute(
        'SELECT id FROM qbank WHERE LOWER(subject)=? AND topic=? ORDER BY id',
        (subject_name.lower(), topic_name)
    ).fetchall()
    id_list = [r['id'] for r in all_ids]

    try:
        index = id_list.index(qid)
    except ValueError:
        conn.close()
        return "<h2>Answer not found</h2>"

    prev_qid = id_list[index-1] if index > 0 else None
    next_qid = id_list[index+1] if index < len(id_list)-1 else None
    is_last_question = index == len(id_list) - 1

    q = conn.execute('SELECT * FROM qbank WHERE id=?', (qid,)).fetchone()
    bookmarked = is_bookmarked(conn, user_id, qid)
    user_note = get_user_note(conn, user_id, qid)
    
    # Get next topic for navigation
    next_topic = get_next_topic(conn, subject_name, topic_name) if is_last_question else None
    
    conn.close()

    return render_template(
        'answer.html',
        subject=subject_name,
        topic=topic_name,
        q=q,
        current_index=index + 1,
        total=len(id_list),
        prev_qid=prev_qid,
        next_qid=next_qid,
        is_last_question=is_last_question,
        next_topic=next_topic,
        bookmarked=bookmarked,
        user_note=user_note
    )

# Add this line before if __name__ == '__main__':
register_dynamic_db_routes(app, ensure_user_session)
register_mcq_routes(app)
app.register_blueprint(test_bp)

if __name__ == '__main__':
    app.run(debug=True)
