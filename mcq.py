# mcq.py - MCQ Management Module for MBBS QBank
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from datetime import datetime, timedelta
import json
import random
from dynamic_db_handler import dynamic_db_handler
# Persistent DB file paths on Render
USER_DB_FILE = '/var/data/admin_users.db'
GENERAL_MCQ_DB_FILE = '/var/data/general_mcq.db'



# Create MCQ Blueprint
mcq_bp = Blueprint('mcq', __name__, url_prefix='/mcq')


# MCQ Database Configuration
def get_mcq_db_connection(subject=None):
    """Get connection to appropriate MCQ database"""
    if subject:
        # Find MCQ database for specific subject
        mcq_databases = dynamic_db_handler.discovered_databases.get('mcq', [])
        for db_info in mcq_databases:
            db_file = db_info['file']
            if subject.lower() in db_file.lower():
                return dynamic_db_handler.get_connection(db_file)
    
    # Default to first available MCQ database
    mcq_databases = dynamic_db_handler.discovered_databases.get('mcq', [])
    if mcq_databases:
        return dynamic_db_handler.get_connection(mcq_databases[0]['file'])
    
    # Fallback: create default MCQ database
    return create_default_mcq_database()


def get_user_db_connection():
    """Get centralized user database connection"""
    return sqlite3.connect(USER_DB_FILE)

def create_default_mcq_database():
    """Create a default MCQ database if none exists"""
    conn = sqlite3.connect(GENERAL_MCQ_DB_FILE)

    conn.row_factory = sqlite3.Row
    
    # Create MCQ questions table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mcq_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            chapter TEXT,
            topic TEXT NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            explanation TEXT,
            difficulty TEXT DEFAULT 'medium',
            year_of_question INTEGER,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create MCQ tests table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mcq_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic_filter TEXT,
            difficulty_filter TEXT,
            total_questions INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL,
            created_by INTEGER,
            is_public INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create MCQ test questions junction table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mcq_test_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            question_order INTEGER NOT NULL,
            FOREIGN KEY (test_id) REFERENCES mcq_tests (id),
            FOREIGN KEY (question_id) REFERENCES mcq_questions (id)
        )
    ''')
    
    conn.commit()
    return conn


def ensure_user_session():
    """Check if user is logged in"""
    return session.get('user_id')


# --------------------
# DEBUG FUNCTIONS
# --------------------


def debug_mcq_database_schema():
    """Debug MCQ database schema and fix missing columns"""
    try:
        conn = get_mcq_db_connection()
        
        debug_output = []
        debug_output.append("🔍 MCQ Database Debug Information:")
        debug_output.append("=" * 50)
        
        # Check if mcq_tests table exists
        tables = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name = 'mcq_tests'
        """).fetchall()
        
        if not tables:
            debug_output.append("❌ mcq_tests table does not exist!")
            debug_output.append("Creating mcq_tests table...")
            create_default_mcq_database()
            debug_output.append("✅ MCQ database tables created successfully")
            return "\n".join(debug_output)
        
        debug_output.append("✅ mcq_tests table exists")
        
        # Get current table schema
        schema = conn.execute("PRAGMA table_info(mcq_tests)").fetchall()
        
        debug_output.append("\n📊 Current mcq_tests table columns:")
        existing_columns = []
        for col in schema:
            debug_output.append(f"  - {col[1]} ({col[2]}) - NOT NULL: {bool(col[3])} - Default: {col[4]}")
            existing_columns.append(col[1])
        
        # Check for missing columns
        required_columns = [
            'id', 'test_name', 'subject', 'topic_filter', 
            'difficulty_filter', 'total_questions', 'duration_minutes', 
            'created_by', 'is_public', 'created_at'
        ]
        
        missing_columns = []
        for col in required_columns:
            if col not in existing_columns:
                missing_columns.append(col)
        
        debug_output.append(f"\n🔍 Missing columns: {missing_columns if missing_columns else 'None'}")
        
        # Fix missing columns
        if missing_columns:
            debug_output.append("\n🔧 Adding missing columns...")
            
            column_definitions = {
                'topic_filter': 'TEXT',
                'difficulty_filter': 'TEXT',
                'created_by': 'INTEGER',
                'is_public': 'INTEGER DEFAULT 1'
            }
            
            for col in missing_columns:
                if col in column_definitions:
                    try:
                        alter_sql = f"ALTER TABLE mcq_tests ADD COLUMN {col} {column_definitions[col]}"
                        conn.execute(alter_sql)
                        debug_output.append(f"  ✅ Added column: {col}")
                    except sqlite3.OperationalError as e:
                        debug_output.append(f"  ❌ Error adding {col}: {e}")
            
            conn.commit()
        
        # Test a simple query
        debug_output.append("\n🧪 Testing difficulty_filter column access...")
        try:
            test_query = conn.execute("SELECT difficulty_filter FROM mcq_tests LIMIT 1").fetchall()
            debug_output.append("  ✅ difficulty_filter column accessible")
        except sqlite3.OperationalError as e:
            debug_output.append(f"  ❌ Error accessing difficulty_filter: {e}")
        
        # Count existing records
        count = conn.execute("SELECT COUNT(*) FROM mcq_tests").fetchone()[0]
        debug_output.append(f"\n📊 Total tests in database: {count}")
        
        conn.close()
        return "\n".join(debug_output)
        
    except Exception as e:
        return f"Debug error: {str(e)}"


def fix_mcq_schema_immediately():
    """Quick fix for missing difficulty_filter column"""
    try:
        conn = get_mcq_db_connection()
        
        # Try to add missing columns
        missing_columns = [
            "ALTER TABLE mcq_tests ADD COLUMN topic_filter TEXT",
            "ALTER TABLE mcq_tests ADD COLUMN difficulty_filter TEXT", 
            "ALTER TABLE mcq_tests ADD COLUMN created_by INTEGER",
            "ALTER TABLE mcq_tests ADD COLUMN is_public INTEGER DEFAULT 1"
        ]
        
        for sql in missing_columns:
            try:
                conn.execute(sql)
                print(f"✅ Executed: {sql}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    print(f"❌ Error: {e}")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error fixing schema: {e}")
        return False


def fix_mcq_questions_schema():
    """Fix missing columns in mcq_questions table"""
    try:
        conn = get_mcq_db_connection()
        
        # Add missing columns for mcq_questions table, including chapter
        missing_columns = [
            "ALTER TABLE mcq_questions ADD COLUMN chapter TEXT",
            "ALTER TABLE mcq_questions ADD COLUMN year_of_question INTEGER",
            "ALTER TABLE mcq_questions ADD COLUMN source TEXT",
            "ALTER TABLE mcq_questions ADD COLUMN explanation TEXT",
            "ALTER TABLE mcq_questions ADD COLUMN difficulty TEXT DEFAULT 'medium'"
        ]
        
        for sql in missing_columns:
            try:
                conn.execute(sql)
                print(f"✅ Executed: {sql}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    print(f"❌ Error: {e}")
                else:
                    print(f"✅ Column already exists: {sql.split()[-2]}")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error fixing mcq_questions schema: {e}")
        return False


def fix_mcq_database_schema():
    """Fix missing difficulty_filter column"""
    try:
        conn = get_mcq_db_connection()
        
        # Try to add the missing column
        conn.execute("ALTER TABLE mcq_tests ADD COLUMN difficulty_filter TEXT")
        conn.commit()
        conn.close()
        print("✅ Added missing difficulty_filter column")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("✅ Column already exists")
        else:
            print(f"❌ Error: {e}")
def get_mcq_chapters(subject):
    conn = get_mcq_db_connection(subject)
    try:
        chapters_rows = conn.execute('''
            SELECT DISTINCT chapter
            FROM mcq_questions
            WHERE subject = ? AND chapter IS NOT NULL AND chapter != ''
            ORDER BY chapter
        ''', (subject,))
        return [row['chapter'] for row in chapters_rows]
    finally:
        conn.close()

def get_chapters_with_topics(subject):
    conn = get_mcq_db_connection(subject)
    try:
        rows = conn.execute('''
            SELECT DISTINCT chapter, topic
            FROM mcq_questions
            WHERE subject = ? AND chapter IS NOT NULL AND chapter != '' AND topic IS NOT NULL AND topic != ''
            ORDER BY chapter, topic
        ''', (subject,)).fetchall()
        
        chapter_map = {}
        for row in rows:
            chapter = row['chapter']
            topic = row['topic']
            if chapter not in chapter_map:
                chapter_map[chapter] = []
            if topic not in chapter_map[chapter]:
                chapter_map[chapter].append(topic)
        
        # Convert to list of dicts if you prefer
        chapter_topics_list = [{"chapter": ch, "topics": ts} for ch, ts in chapter_map.items()]
        return chapter_topics_list
    finally:
        conn.close()

# --------------------
# HELPER FUNCTIONS
# --------------------


def get_all_mcq_subjects():
    """Get all subjects from MCQ databases"""
    subjects = set()
    mcq_databases = dynamic_db_handler.discovered_databases.get('mcq', [])
    
    for db_info in mcq_databases:
        try:
            conn = dynamic_db_handler.get_connection(db_info['file'])
            subject_rows = conn.execute('SELECT DISTINCT subject FROM mcq_questions').fetchall()
            subjects.update([row['subject'] for row in subject_rows])
            conn.close()
        except Exception as e:
            print(f"Error getting subjects from {db_info['file']}: {e}")
    
    return sorted(list(subjects))


def get_mcq_topics(subject):
    """Get all topics for a specific subject"""
    conn = get_mcq_db_connection(subject)
    try:
        topics = conn.execute('''
            SELECT DISTINCT topic, COUNT(*) as question_count
            FROM mcq_questions 
            WHERE subject = ? 
            GROUP BY topic 
            ORDER BY topic
        ''', (subject,)).fetchall()
        return topics
    finally:
        conn.close()


# --------------------
# MCQ ROUTES
# --------------------


@mcq_bp.route('/')
def mcq_home():
    """MCQ Home page showing all subjects"""
    # Auto-fix schema issues for both tables
    try:
        fix_mcq_schema_immediately()    # For tests table
        fix_mcq_questions_schema()      # For questions table (NEW)
    except Exception as e:
        print(f"Schema fix error: {e}")
    
    subjects = get_all_mcq_subjects()
    
    # Get question counts for each subject
    subject_stats = []
    for subject in subjects:
        conn = get_mcq_db_connection(subject)
        try:
            stats = conn.execute('''
                SELECT 
                    COUNT(*) as total_questions,
                    COUNT(DISTINCT topic) as topics,
                    AVG(CASE WHEN difficulty = 'easy' THEN 1 WHEN difficulty = 'medium' THEN 2 ELSE 3 END) as avg_difficulty
                FROM mcq_questions 
                WHERE subject = ?
            ''', (subject,)).fetchone()
            
            subject_stats.append({
                'name': subject,
                'total_questions': stats['total_questions'],
                'topics': stats['topics'],
                'avg_difficulty': round(stats['avg_difficulty'], 1) if stats['avg_difficulty'] else 2.0
            })
        finally:
            conn.close()
    
    return render_template('mcq/mcq_home.html', subjects=subject_stats)


@mcq_bp.route('/subject/<subject_name>')
def mcq_subject(subject_name):
    chapter_topics = get_chapters_with_topics(subject_name)
    
    conn = get_mcq_db_connection(subject_name)
    try:
        tests = conn.execute('''
            SELECT id, test_name, total_questions, duration_minutes, difficulty_filter
            FROM mcq_tests 
            WHERE subject = ? AND is_public = 1
            ORDER BY created_at DESC
        ''', (subject_name,)).fetchall()
    finally:
        conn.close()
    
    return render_template('mcq/mcq_subject.html', 
                           subject=subject_name, 
                           chapter_topics=chapter_topics, 
                           tests=tests)

@mcq_bp.route('/practice/<subject_name>/<topic_name>')
def mcq_practice_topic(subject_name, topic_name):
    """Practice MCQs for a specific topic"""
    user_id = ensure_user_session()
    if not user_id:
        flash('Please login to practice MCQs', 'info')
        return redirect(url_for('login'))
    
    # Get questions for this topic
    conn = get_mcq_db_connection(subject_name)
    try:
        questions = conn.execute('''
            SELECT * FROM mcq_questions 
            WHERE subject = ? AND topic = ?
            ORDER BY RANDOM()
        ''', (subject_name, topic_name)).fetchall()
        
        if not questions:
            flash('No MCQ questions found for this topic', 'warning')
            return redirect(url_for('mcq.mcq_subject', subject_name=subject_name))
        
    finally:
        conn.close()
    
    return render_template('mcq/mcq_practice.html', 
                         subject=subject_name,
                         topic=topic_name,
                         questions=questions)


@mcq_bp.route('/test/<int:test_id>')
def mcq_test(test_id):
    """Take a specific MCQ test"""
    user_id = ensure_user_session()
    if not user_id:
        flash('Please login to take tests', 'info')
        return redirect(url_for('login'))
    
    # Get test details
    conn = get_mcq_db_connection()
    try:
        test = conn.execute('SELECT * FROM mcq_tests WHERE id = ?', (test_id,)).fetchone()
        if not test:
            flash('Test not found', 'error')
            return redirect(url_for('mcq.mcq_home'))
        
        # Get test questions
        test_questions = conn.execute('''
            SELECT mq.*, mtq.question_order
            FROM mcq_questions mq
            JOIN mcq_test_questions mtq ON mq.id = mtq.question_id
            WHERE mtq.test_id = ?
            ORDER BY mtq.question_order
        ''', (test_id,)).fetchall()
        
    finally:
        conn.close()
    
    return render_template('mcq/mcq_test.html', 
                         test=test, 
                         questions=test_questions)


@mcq_bp.route('/submit_test', methods=['POST'])
def submit_mcq_test():
    """Submit and grade MCQ test"""
    user_id = ensure_user_session()
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login first'})
    
    try:
        data = request.get_json()
        test_id = data.get('test_id')
        answers = data.get('answers', {})  # {question_id: selected_option}
        time_taken = data.get('time_taken', 0)  # in minutes
        
        # Get test and questions
        conn = get_mcq_db_connection()
        
        test = conn.execute('SELECT * FROM mcq_tests WHERE id = ?', (test_id,)).fetchone()
        if not test:
            return jsonify({'success': False, 'message': 'Test not found'})
        
        # Get correct answers
        test_questions = conn.execute('''
            SELECT mq.id, mq.correct_answer, mq.explanation
            FROM mcq_questions mq
            JOIN mcq_test_questions mtq ON mq.id = mtq.question_id
            WHERE mtq.test_id = ?
        ''', (test_id,)).fetchall()
        
        # Grade the test
        total_questions = len(test_questions)
        correct_answers = 0
        results = {}
        
        for question in test_questions:
            question_id = str(question['id'])
            user_answer = answers.get(question_id)
            correct_answer = question['correct_answer']
            
            is_correct = user_answer == correct_answer
            if is_correct:
                correct_answers += 1
            
            results[question_id] = {
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct,
                'explanation': question['explanation']
            }
        
        percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        # Save result to centralized user database
        user_conn = get_user_db_connection()
        user_conn.row_factory = sqlite3.Row
        
        # Create MCQ results table if it doesn't exist
        user_conn.execute('''
            CREATE TABLE IF NOT EXISTS mcq_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                test_id INTEGER NOT NULL,
                test_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                percentage REAL NOT NULL,
                time_taken_minutes INTEGER NOT NULL,
                detailed_results TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        user_conn.execute('''
            INSERT INTO mcq_results 
            (user_id, test_id, test_name, subject, score, total_questions, percentage, time_taken_minutes, detailed_results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, test_id, test['test_name'], test['subject'], 
              correct_answers, total_questions, percentage, time_taken, json.dumps(results)))
        
        user_conn.commit()
        user_conn.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'score': correct_answers,
            'total': total_questions,
            'percentage': round(percentage, 1),
            'results': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@mcq_bp.route('/results')
def mcq_results():
    """Show user's MCQ test results"""
    user_id = ensure_user_session()
    if not user_id:
        flash('Please login to view results', 'info')
        return redirect(url_for('login'))
    
    user_conn = get_user_db_connection()
    user_conn.row_factory = sqlite3.Row
    
    try:
        # Check if results table exists
        user_conn.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="mcq_results"')
        
        results = user_conn.execute('''
            SELECT * FROM mcq_results 
            WHERE user_id = ? 
            ORDER BY completed_at DESC
        ''', (user_id,)).fetchall()
        
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        results = []
    finally:
        user_conn.close()
    
    return render_template('mcq/mcq_results.html', results=results)


@mcq_bp.route('/create_test', methods=['GET', 'POST'])
def create_mcq_test():
    """Create a new MCQ test"""
    user_id = ensure_user_session()
    if not user_id:
        flash('Please login to create tests', 'info')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        test_name = request.form['test_name']
        subject = request.form['subject']
        topic_filter = request.form.get('topic_filter', '')
        difficulty_filter = request.form.get('difficulty_filter', '')
        num_questions = int(request.form['num_questions'])
        duration = int(request.form['duration'])
        
        try:
            # Get questions based on filters
            conn = get_mcq_db_connection(subject)
            
            query = 'SELECT * FROM mcq_questions WHERE subject = ?'
            params = [subject]
            
            if topic_filter:
                query += ' AND topic = ?'
                params.append(topic_filter)
            
            if difficulty_filter:
                query += ' AND difficulty = ?'
                params.append(difficulty_filter)
            
            query += ' ORDER BY RANDOM() LIMIT ?'
            params.append(num_questions)
            
            questions = conn.execute(query, params).fetchall()
            
            if len(questions) < num_questions:
                flash(f'Only {len(questions)} questions available with current filters', 'warning')
                return redirect(request.url)
            
            # Create test
            cursor = conn.execute('''
                INSERT INTO mcq_tests (test_name, subject, topic_filter, difficulty_filter, total_questions, duration_minutes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (test_name, subject, topic_filter, difficulty_filter, num_questions, duration, user_id))
            
            test_id = cursor.lastrowid
            
            # Add questions to test
            for i, question in enumerate(questions):
                conn.execute('''
                    INSERT INTO mcq_test_questions (test_id, question_id, question_order)
                    VALUES (?, ?, ?)
                ''', (test_id, question['id'], i + 1))
            
            conn.commit()
            conn.close()
            
            flash('Test created successfully!', 'success')
            return redirect(url_for('mcq.mcq_test', test_id=test_id))
            
        except Exception as e:
            flash(f'Error creating test: {str(e)}', 'error')
    
    subjects = get_all_mcq_subjects()
    return render_template('mcq/create_test.html', subjects=subjects)


@mcq_bp.route('/api/topics/<subject>')
def api_get_topics(subject):
    """API endpoint to get topics for a subject"""
    topics = get_mcq_topics(subject)
    return jsonify([{'name': topic['topic'], 'count': topic['question_count']} for topic in topics])


# --------------------
# ADMIN MCQ ROUTES
# --------------------


@mcq_bp.route('/admin/add_question', methods=['GET', 'POST'])
def admin_add_mcq_question():
    """Admin route to add MCQ questions"""
    user_id = ensure_user_session()
    if not user_id:
        flash('Please login to access admin features', 'info')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            subject = request.form['subject']
            chapter = request.form.get('chapter', '')               # <--- Added capturing chapter
            topic = request.form['topic']
           
            question = request.form['question']
            option_a = request.form['option_a']
            option_b = request.form['option_b']
            option_c = request.form['option_c']
            option_d = request.form['option_d']
            correct_answer = request.form['correct_answer']
            explanation = request.form.get('explanation', '')
            difficulty = request.form.get('difficulty', 'medium')
            year_of_question = request.form.get('year_of_question')
            source = request.form.get('source', '')
            
            conn = get_mcq_db_connection(subject)
            conn.execute('''
                INSERT INTO mcq_questions 
                (subject, chapter, topic, question, option_a, option_b, option_c, option_d, 
                 correct_answer, explanation, difficulty, year_of_question, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (subject, chapter, topic, question, option_a, option_b, option_c, option_d,
                  correct_answer, explanation, difficulty, 
                  int(year_of_question) if year_of_question else None, source))
            
            conn.commit()
            conn.close()
            
            flash('MCQ question added successfully!', 'success')
            return redirect(request.url)
            
        except Exception as e:
            flash(f'Error adding question: {str(e)}', 'error')
    
    subjects = get_all_mcq_subjects()
    return render_template('mcq/admin_add_question.html', subjects=subjects)


# --------------------
# DEBUG ROUTES
# --------------------


@mcq_bp.route('/admin/debug_schema')
def debug_mcq_schema():
    """Debug route to check and fix MCQ database schema"""
    user_id = ensure_user_session()
    if not user_id:
        return "Please login to access debug features. <a href='/login'>Login</a>"
    
    result = debug_mcq_database_schema()
    
    return f"""
    <h2>🔍 MCQ Database Schema Debug</h2>
    <div style="background: #f8f9fa; padding: 20px; border-radius: 6px; font-family: monospace; white-space: pre-line;">
    {result}
    </div>
    <p><a href="/mcq/">Back to MCQ Home</a></p>
    <p><a href="/admin/dynamic_db_manager">Database Manager</a></p>
    """
@mcq_bp.route('/admin/debug_add_question', methods=['GET', 'POST'])
def debug_add_question():
    """Debug route to test MCQ question addition with detailed logging"""
    user_id = ensure_user_session()
    if not user_id:
        return "Please login to access debug features. <a href='/login'>Login</a>"
    
    debug_info = []
    
    if request.method == 'POST':
        debug_info.append("🔍 POST Request Received")
        debug_info.append(f"Form data: {dict(request.form)}")
        
        try:
            # Extract form data with debugging
            subject = request.form.get('subject', '')
            chapter = request.form.get('chapter', '')                   # <--- Added capturing chapter here
            topic = request.form.get('topic', '')
            question = request.form.get('question', '')
            option_a = request.form.get('option_a', '')
            option_b = request.form.get('option_b', '')
            option_c = request.form.get('option_c', '')
            option_d = request.form.get('option_d', '')
            correct_answer = request.form.get('correct_answer', '')
            explanation = request.form.get('explanation', '')
            difficulty = request.form.get('difficulty', 'medium')
            year_of_question = request.form.get('year_of_question', '')
            source = request.form.get('source', '')
            
            debug_info.append(f"Subject: '{subject}'")
            debug_info.append(f"Chapter: '{chapter}'")
            debug_info.append(f"Topic: '{topic}'")
            debug_info.append(f"Question: '{question[:50]}...'")
            debug_info.append(f"Correct Answer: '{correct_answer}'")
            
            # Validation checks
            if not all([subject, topic, question, option_a, option_b, option_c, option_d, correct_answer]):
                missing_fields = []
                if not subject: missing_fields.append('subject')
                if not topic: missing_fields.append('topic')
                if not question: missing_fields.append('question')
                if not option_a: missing_fields.append('option_a')
                if not option_b: missing_fields.append('option_b')
                if not option_c: missing_fields.append('option_c')
                if not option_d: missing_fields.append('option_d')
                if not correct_answer: missing_fields.append('correct_answer')
                
                debug_info.append(f"❌ Missing required fields: {missing_fields}")
                return create_debug_response(debug_info, "Validation failed")
            
            debug_info.append("✅ All required fields present")
            
            # Test database connection
            conn = get_mcq_db_connection(subject)
            debug_info.append(f"✅ Database connection established")
            
            # Check table schema
            schema = conn.execute("PRAGMA table_info(mcq_questions)").fetchall()
            columns = [col[1] for col in schema]
            debug_info.append(f"Available columns: {columns}")
            
            # Check for required columns
            required_cols = ['subject', 'chapter', 'topic', 'question', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']
            missing_cols = [col for col in required_cols if col not in columns]
            if missing_cols:
                debug_info.append(f"❌ Missing table columns: {missing_cols}")
                # Try to fix schema
                fix_mcq_questions_schema()
                debug_info.append("🔧 Attempted schema fix")
            
            # Test insert query
            debug_info.append("🧪 Attempting to insert question...")
            
            cursor = conn.execute('''
                INSERT INTO mcq_questions 
                (subject, chapter, topic, question, option_a, option_b, option_c, option_d, 
                 correct_answer, explanation, difficulty, year_of_question, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (subject, chapter, topic, question, option_a, option_b, option_c, option_d,
                  correct_answer, explanation, difficulty, 
                  int(year_of_question) if year_of_question else None, source))
            
            question_id = cursor.lastrowid
            debug_info.append(f"✅ Question inserted with ID: {question_id}")
            
            conn.commit()
            debug_info.append("✅ Database changes committed")
            
            # Verify insertion
            verify = conn.execute('SELECT * FROM mcq_questions WHERE id = ?', (question_id,)).fetchone()
            if verify:
                debug_info.append(f"✅ Question verified in database: {verify['subject']} - {verify['topic']}")
            else:
                debug_info.append("❌ Question not found after insertion")
            
            conn.close()
            debug_info.append("✅ Database connection closed")
            
            return create_debug_response(debug_info, "SUCCESS: Question added successfully!")
            
        except Exception as e:
            debug_info.append(f"❌ ERROR: {str(e)}")
            import traceback
            debug_info.append(f"Traceback: {traceback.format_exc()}")
            return create_debug_response(debug_info, f"FAILED: {str(e)}")
    
    # GET request - show debug form
    subjects = get_all_mcq_subjects()
    
    return f"""
    <h2>🔍 MCQ Add Question Debug</h2>
    
    <form method="POST" style="max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
        <div style="margin: 15px 0;">
            <label><strong>Subject:</strong></label><br>
            <select name="subject" required style="width: 100%; padding: 8px; margin: 5px 0;">
                <option value="">Select Subject</option>
                <option value="Pathology">Pathology</option>
                <option value="Anatomy">Anatomy</option>
                <option value="Physiology">Physiology</option>
            </select>
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Chapter:</strong></label><br>
            <input type="text" name="chapter" placeholder="e.g., Chapter 1, Introduction" style="width: 100%; padding: 8px; margin: 5px 0;">
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Topic:</strong></label><br>
            <input type="text" name="topic" required placeholder="e.g., Cardiovascular System" style="width: 100%; padding: 8px; margin: 5px 0;">
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Question:</strong></label><br>
            <textarea name="question" required placeholder="Enter question here..." style="width: 100%; padding: 8px; margin: 5px 0; height: 80px;"></textarea>
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Option A:</strong></label><br>
            <input type="text" name="option_a" required style="width: 100%; padding: 8px; margin: 5px 0;">
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Option B:</strong></label><br>
            <input type="text" name="option_b" required style="width: 100%; padding: 8px; margin: 5px 0;">
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Option C:</strong></label><br>
            <input type="text" name="option_c" required style="width: 100%; padding: 8px; margin: 5px 0;">
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Option D:</strong></label><br>
            <input type="text" name="option_d" required style="width: 100%; padding: 8px; margin: 5px 0;">
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Correct Answer:</strong></label><br>
            <select name="correct_answer" required style="width: 100%; padding: 8px; margin: 5px 0;">
                <option value="">Select Correct Answer</option>
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
                <option value="D">D</option>
            </select>
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Explanation (Optional):</strong></label><br>
            <textarea name="explanation" placeholder="Explain the answer..." style="width: 100%; padding: 8px; margin: 5px 0; height: 60px;"></textarea>
        </div>
        
        <div style="margin: 15px 0;">
            <label><strong>Difficulty:</strong></label><br>
            <select name="difficulty" style="width: 100%; padding: 8px; margin: 5px 0;">
                <option value="easy">Easy</option>
                <option value="medium" selected>Medium</option>
                <option value="hard">Hard</option>
            </select>
        </div>
        
        <div style="margin: 15px 0;">
            <input type="submit" value="Debug Add Question" style="background: #007bff; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer;">
        </div>
    </form>
    
    <p><a href="/mcq/admin/add_question">Back to Regular Add Question</a></p>
    <p><a href="/mcq/">Back to MCQ Home</a></p>
    """


def create_debug_response(debug_info, summary):
    """Create formatted debug response"""
    return f"""
    <h2>{summary}</h2>
    <div style="background: #f8f9fa; padding: 20px; border-radius: 6px; font-family: monospace; white-space: pre-line; max-width: 800px; margin: 20px auto;">
    {chr(10).join(debug_info)}
    </div>
    <p><a href="/mcq/admin/debug_add_question">Try Again</a></p>
    <p><a href="/mcq/">Back to MCQ Home</a></p>
    <p><a href="/mcq/subject/Pathology">Check Pathology Questions</a></p>
    """



@mcq_bp.route('/admin/debug_questions_schema')
def debug_mcq_questions_schema():
    """Debug route to check and fix MCQ questions table schema"""
    user_id = ensure_user_session()
    if not user_id:
        return "Please login to access debug features. <a href='/login'>Login</a>"
    
    try:
        conn = get_mcq_db_connection()
        
        # Get current schema
        schema = conn.execute("PRAGMA table_info(mcq_questions)").fetchall()
        
        schema_info = "🔍 Current mcq_questions table schema:\n\n"
        for col in schema:
            schema_info += f"- {col[1]} ({col[2]}) - NOT NULL: {bool(col[3])}\n"
        
        # Check for missing columns
        existing_columns = [col[1] for col in schema]
        required_columns = ['id', 'subject', 'chapter', 'topic', 'question', 'option_a', 'option_b', 
                          'option_c', 'option_d', 'correct_answer', 'explanation', 
                          'difficulty', 'year_of_question', 'source', 'created_at']
        
        missing_columns = [col for col in required_columns if col not in existing_columns]
        
        if missing_columns:
            schema_info += f"\n❌ Missing columns: {missing_columns}\n"
            
            # Fix missing columns
            column_definitions = {
                'chapter': 'TEXT',
                'year_of_question': 'INTEGER',
                'source': 'TEXT',
                'explanation': 'TEXT',
                'difficulty': 'TEXT DEFAULT \"medium\"'
            }
            
            for col in missing_columns:
                if col in column_definitions:
                    try:
                        alter_sql = f"ALTER TABLE mcq_questions ADD COLUMN {col} {column_definitions[col]}"
                        conn.execute(alter_sql)
                        schema_info += f"✅ Added column: {col}\n"
                    except sqlite3.OperationalError as e:
                        schema_info += f"❌ Error adding {col}: {e}\n"
            
            conn.commit()
        else:
            schema_info += "\n✅ All required columns present\n"
        
        conn.close()
        
        return f"""
        <h2>🔍 MCQ Questions Table Schema Debug</h2>
        <div style="background: #f8f9fa; padding: 20px; border-radius: 6px; font-family: monospace; white-space: pre-line;">
        {schema_info}
        </div>
        <p><a href="/mcq/admin/add_question">Try Adding Question Again</a></p>
        <p><a href="/mcq/">Back to MCQ Home</a></p>
        """
        
    except Exception as e:
        return f"<h2>❌ Debug Error:</h2><p>{str(e)}</p>"


def register_mcq_routes(app):
    """Register MCQ blueprint with the Flask app"""
    app.register_blueprint(mcq_bp)
