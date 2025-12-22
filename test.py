from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, session, jsonify
import sqlite3
import os
from dynamic_db_handler import dynamic_db_handler
test_bp = Blueprint('test_bp', __name__, url_prefix='/test', template_folder='templates')
# then the URL becomes /test/tests

# At top of test.py
from dynamic_db_handler import dynamic_db_handler

BASE_TEST_DIR = '/var/data'  # keep if you use it elsewhere

# Auto-create user_responses if missing

def get_test_db_connection():
    """Return connection to the tests database for the current goal, like MCQ does."""
    goal_key = session.get('current_goal')  # 'neet_ug', 'mbbs', etc.





    # Refresh discovery
    dynamic_db_handler.discovered_databases = dynamic_db_handler.discover_databases()
    test_databases = dynamic_db_handler.discovered_databases.get('test', [])

    # 1) Try to find a test DB whose filename contains the goal key
    if goal_key:
        for db_info in test_databases:
            if goal_key.lower() in db_info['file'].lower():
                conn = dynamic_db_handler.get_connection(db_info['file'])
                conn.row_factory = sqlite3.Row
                return conn

    # 2) Fallback: first available test DB
    if test_databases:
        conn = dynamic_db_handler.get_connection(test_databases[0]['file'])
        conn.row_factory = sqlite3.Row
        return conn

    # 3) Last resort: use /var/data/tests.db
    db_path = os.path.join(BASE_TEST_DIR, 'tests.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

# Auto-create user_responses if missing
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            question_id INTEGER,
            user_answer TEXT,
            is_correct INTEGER,
            test_started INTEGER DEFAULT 0,
            test_submitted INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(test _id, user_id, question_id)
        )
    ''')
    conn.commit()


    return conn

# Auto-create user_responses if missing
# Auto-create user_responses if missing


def get_db_connection_for_test(test_id):
    """
    Find and return the exact database connection where the given test_id exists.
    This ensures consistency between submit and review.
    """
    # Refresh discovered databases
    dynamic_db_handler.discovered_databases = dynamic_db_handler.discover_databases()
    test_dbs = dynamic_db_handler.discovered_databases.get('test', [])

    for db_info in test_dbs:
        try:
            conn = dynamic_db_handler.get_connection(db_info['file'])
            conn.row_factory = sqlite3.Row
            # Check if this test exists in this DB
            if conn.execute('SELECT 1 FROM test_info WHERE id = ?', (test_id,)).fetchone():
                return conn  # Found the right one!
        except Exception as e:
            print(f"Error checking {db_info['file']}: {e}")
            if 'conn' in locals():
                conn.close()
            continue

    # If not found in any discovered DB, fallback (should rarely happen)
    conn = get_db_connection_for_test(test_id)  # This already sets row_factory
    return conn
def get_session_db(test_id):
    db_file = session.get(f'test_{test_id}_db_file')
    if not db_file:
        return None
    conn = dynamic_db_handler.get_connection(db_file)
    conn.row_factory = sqlite3.Row
    return conn


@test_bp.route('/tests')
def list_tests():
    user_id = session.get('user_id', 1)
    goal_key = session.get('current_goal')  # 'neet_ug', 'mbbs_prof', etc.
    
    # Get ALL test databases
    dynamic_db_handler.discovered_databases = dynamic_db_handler.discover_databases()
    all_test_dbs = dynamic_db_handler.discovered_databases.get('test', [])
    
    # FILTER by current goal
    goal_test_dbs = []
    if goal_key:
        for db_info in all_test_dbs:
            if goal_key.lower() in db_info['file'].lower():
                goal_test_dbs.append(db_info)
    else:
        goal_test_dbs = all_test_dbs  # No goal = show all
    
    print(f"DEBUG: Goal='{goal_key}', Found {len(goal_test_dbs)} goal-specific test DBs")
    
    all_tests = []
    
    # Query ONLY goal-specific databases
    for db_info in goal_test_dbs:
        try:
            conn = dynamic_db_handler.get_connection(db_info['file'])
            conn.row_factory = sqlite3.Row
            
            tests = conn.execute('''
                SELECT ti.id, ti.test_name, ti.description, ti.duration_minutes,
                    ti.start_time, ti.end_time, ti.created_at,
                    CASE WHEN EXISTS (
                        SELECT 1 FROM user_responses ur 
                        WHERE ur.test_id = ti.id AND ur.user_id = ? AND ur.test_submitted = 1
                    ) THEN 1 ELSE 0 END AS test_submitted
                FROM test_info ti
                ORDER BY ti.created_at DESC
                ''', (user_id,)).fetchall()

            
            # Add DB info
            for test_row in tests:
                    test_dict = dict(test_row)
                    test_dict['database_file'] = os.path.basename(db_info['file'])
                    
                    if test_dict.get('is_locked', 0) == 1:

                    # Locked test: only unlock if user subscribed for this goal
                       if user_sub_status == 'subscribed' and user_sub_goal == goal_key:
                        tests['effective_locked'] = 0  # unlocked for this user
                       else:
                        tests['effective_locked'] = 1  # remains locked
                    else:
                    # Free test
                        tests['effective_locked'] = 0

                    all_tests.append(tests)


                    # 🔥 CHECK COMPLETION IN THIS DB:
                    user_id = session.get('user_id', 1)
                    try:
                        check_conn = dynamic_db_handler.get_connection(db_info['file'])
                        check_conn.row_factory = sqlite3.Row
                        result = check_conn.execute('''
                            SELECT 1 FROM user_responses 
                            WHERE test_id=? AND user_id=? AND test_submitted=1
                        ''', (test_dict['id'], user_id)).fetchone()
                        test_dict['test_submitted'] = 1 if result else 0
                        check_conn.close()
                    except:
                        test_dict['test_submitted'] = 0
                    
                    all_tests.append(test_dict)

            
            conn.close()
        except Exception as e:
            print(f"Error in {db_info['file']}: {e}")
    
    all_tests.sort(key=lambda t: t.get('created_at', ''), reverse=True)
    
    return render_template('test/tests.html', tests=all_tests)


@test_bp.route('/tests/<int:test_id>/questions')
def view_test_questions(test_id):
    conn = get_db_connection_for_test(test_id)
    try:
        test = conn.execute('SELECT * FROM test_info WHERE id = ?', (test_id,)).fetchone()
        if not test:
            abort(404, description="Test not found")

        questions = conn.execute('''
            SELECT subject, topic, question, option_a, option_b, option_c, option_d, 
                   correct_answer, explanation
            FROM test_questions
            WHERE test_id = ?
            ORDER BY subject, topic, id
        ''', (test_id,)).fetchall()

    finally:
        conn.close()

    grouped_questions = {}
    for q in questions:
        grouped_questions.setdefault(q['subject'], {})
        grouped_questions[q['subject']].setdefault(q['topic'], [])
        grouped_questions[q['subject']][q['topic']].append(q)

    return render_template('test/test_questions.html', test=test, grouped_questions=grouped_questions)


# -----------------------------
# Single-question-per-page with independent AJAX marking and skip support
# -----------------------------


@test_bp.route('/tests/<int:test_id>/start')
def start_test(test_id):
    db_file = request.args.get('db_file')  # From template!
    
    if db_file:
        full_path = os.path.join('/var/data', db_file)
        if os.path.exists(full_path):
            # Verify test exists in this DB
            conn = dynamic_db_handler.get_connection(full_path)
            if conn.execute('SELECT 1 FROM test_info WHERE id=?', (test_id,)).fetchone():
                session[f'test_{test_id}_db_file'] = full_path
                print(f"✅ start_test(): test_id={test_id} in {db_file}")
                conn.close()
                # Initialize sessions
                session[f'test_{test_id}_answers'] = {}
                session[f'test_{test_id}_marked'] = []
                session[f'test_{test_id}_skipped'] = []
                return redirect(url_for('test_bp.single_question', test_id=test_id, q_num=1))
            else:
                conn.close()
                flash(f"Test ID {test_id} not found in {db_file}!", "error")
                return redirect(url_for('test_bp.list_tests'))
        else:
            flash(f"Database {db_file} not found!", "error")
            return redirect(url_for('test_bp.list_tests'))
    
    # Fallback if no db_file
    flash("No database specified!", "error")
    return redirect(url_for('test_bp.list_tests'))


@test_bp.route('/tests/<int:test_id>/question/<int:q_num>', methods=['GET', 'POST'])
def single_question(test_id, q_num):
    conn = get_session_db(test_id) 
    if not conn:
     abort(404)
    try:
        questions = conn.execute(
            '''SELECT id, subject, topic, question, option_a, option_b, option_c, option_d, correct_answer
               FROM test_questions WHERE test_id = ? ORDER BY id''',
            (test_id,)
        ).fetchall()
        test = conn.execute('SELECT * FROM test_info WHERE id = ?', (test_id,)).fetchone()
    finally:
        conn.close()

    if not test or not questions or q_num < 1 or q_num > len(questions):
        abort(404)

    question = questions[q_num - 1]

    answer_key = f'test_{test_id}_answers'
    mark_key = f'test_{test_id}_marked'
    skip_key = f'test_{test_id}_skipped'

    if answer_key not in session:
        session[answer_key] = {}
    if mark_key not in session:
        session[mark_key] = []
    if skip_key not in session:
        session[skip_key] = []

    answers = session[answer_key]
    marked = set(session[mark_key])
    skipped = set(session[skip_key])

    if request.method == 'POST':
        selected_option = request.form.get('answer')
        nav = request.form.get('nav')  # previous, next, submit, skip

        if nav == 'skip':
            # Mark the question as skipped
            skipped.add(str(question['id']))
            session[skip_key] = list(skipped)
            # Remove answer if it exists, since it's skipped
            if str(question['id']) in answers:
                del answers[str(question['id'])]
                session[answer_key] = answers
            # Navigate forward if possible
            next_q_num = q_num + 1 if q_num < len(questions) else q_num
            return redirect(url_for('test_bp.single_question', test_id=test_id, q_num=next_q_num))

        if nav in ('next', 'submit'):
            if not selected_option:
                flash("Please select an option or choose Skip.")
                return render_template(
                    'test/single_question.html',
                    test=test,
                    question=question,
                    q_num=q_num,
                    total=len(questions),
                    selected_answer=answers.get(str(question['id']), None),
                    marked_questions=marked,
                    skipped_questions=skipped,
                    duration_minutes=test['duration_minutes']
                )
            # Save answer and remove from skipped if any
            answers[str(question['id'])] = selected_option
            session[answer_key] = answers
            if str(question['id']) in skipped:
                skipped.remove(str(question['id']))
                session[skip_key] = list(skipped)

        elif nav == 'previous':
            # Save answer if selected before going back
            if selected_option:
                answers[str(question['id'])] = selected_option
                session[answer_key] = answers

        # Navigate accordingly
        if nav == 'previous':
            prev_q_num = max(1, q_num - 1)
            return redirect(url_for('test_bp.single_question', test_id=test_id, q_num=prev_q_num))
        elif nav == 'next':
            next_q_num = min(len(questions), q_num + 1)
            return redirect(url_for('test_bp.single_question', test_id=test_id, q_num=next_q_num))
        elif nav == 'submit':
            return redirect(url_for('test_bp.submit_test', test_id=test_id))

    return render_template(
        'test/single_question.html',
        test=test,
        question=question,
        q_num=q_num,
        total=len(questions),
        selected_answer=answers.get(str(question['id']), None),
        marked_questions=marked,
        skipped_questions=skipped,
        duration_minutes=test['duration_minutes']
    )


# AJAX toggle mark
@test_bp.route('/tests/<int:test_id>/question/<int:q_num>/toggle_mark', methods=['POST'])
def toggle_mark_ajax(test_id, q_num):
    conn = get_db_connection_for_test(test_id)
    try:
        questions = conn.execute('SELECT id FROM test_questions WHERE test_id = ? ORDER BY id', (test_id,)).fetchall()
    finally:
        conn.close()

    if not questions or q_num < 1 or q_num > len(questions):
        return jsonify({'success': False, 'error': 'Invalid question'}), 400

    q_id_str = str(questions[q_num - 1]['id'])

    mark_key = f'test_{test_id}_marked'
    if mark_key not in session:
        session[mark_key] = []
    marked = set(session[mark_key])

    if q_id_str in marked:
        marked.remove(q_id_str)
        marked_now = False
    else:
        marked.add(q_id_str)
        marked_now = True

    session[mark_key] = list(marked)

    return jsonify({'success': True, 'marked': marked_now})


@test_bp.route('/tests/<int:test_id>/review')
def review_test(test_id):
    conn = get_session_db(test_id)
    try:
        questions = conn.execute('''SELECT id FROM test_questions WHERE test_id = ? ORDER BY id''', (test_id,)).fetchall()
        test = conn.execute('SELECT * FROM test_info WHERE id = ?', (test_id,)).fetchone()
    finally:
        conn.close()
    if not test or not questions:
        abort(404)

    answer_key = f'test_{test_id}_answers'
    mark_key = f'test_{test_id}_marked'
    skip_key = f'test_{test_id}_skipped'

    answers = session.get(answer_key, {})
    marked = set(session.get(mark_key, []))
    skipped = set(session.get(skip_key, []))

    return render_template('test/review.html',
                           test=test,
                           questions=questions,
                           answers=answers,
                           marked=marked,
                           skipped=skipped)

@test_bp.route('/tests/<int:test_id>/review-attempted')
def review_attempted(test_id):
    print(f"DEBUG REVIEW_ATTEMPTED: test_id={test_id}")
    conn = get_session_db(test_id)
    if not conn:
     return redirect(url_for('test_bp.list_tests'))

      
    try:
        test = conn.execute('SELECT * FROM test_info WHERE id = ?', (test_id,)).fetchone()
        print(f"DEBUG: Test '{test['test_name'] if test else 'NOT FOUND'}'")
        if not test:
            flash(f"Test ID {test_id} not found!")
            return redirect(url_for('test_bp.list_tests'))
        
        user_id = session.get('user_id', 1)
        print(f"DEBUG: Looking for user_id={user_id}")
        
        all_questions = conn.execute('''
            SELECT tq.*, ur.user_answer, ur.is_correct
            FROM test_questions tq
            LEFT JOIN user_responses ur ON tq.id = ur.question_id 
                AND ur.test_id = ? AND ur.user_id = ?
            WHERE tq.test_id = ?
            ORDER BY tq.id
        ''', (test_id, user_id, test_id)).fetchall()
        print(f"DEBUG: Total questions found: {len(all_questions)}")
        
        correct_questions = [q for q in all_questions if q['is_correct'] == 1]
        incorrect_questions = [q for q in all_questions if q['is_correct'] == 0]
        unanswered_questions = [q for q in all_questions if q['is_correct'] is None]
        
        print(f"DEBUG: Correct={len(correct_questions)}, Wrong={len(incorrect_questions)}, Unanswered={len(unanswered_questions)}")
        
    finally:
        conn.close()
    
    return render_template('test/review_attempted.html',
                           test=test,
                           correct_count=len(correct_questions),
                           incorrect_count=len(incorrect_questions),
                           unanswered_count=len(unanswered_questions),
                           correct_questions=correct_questions,
                           incorrect_questions=incorrect_questions,
                           unanswered_questions=unanswered_questions)

@test_bp.route('/tests/<int:test_id>/review/<string:filter_type>/<int:q_index>')
def review_question(test_id, filter_type, q_index):
    print(f"DEBUG: review_question - test_id={test_id}, filter={filter_type}, q_index={q_index}")
    
    conn = get_session_db(test_id)
    if not conn:
     return redirect(url_for('test_bp.review_attempted', test_id=test_id))
    
    try:
        # 1. Verify test exists
        test = conn.execute('SELECT * FROM test_info WHERE id = ?', (test_id,)).fetchone()
        if not test:
            flash(f"Test ID {test_id} not found!")
            return redirect(url_for('test_bp.list_tests'))
        
        user_id = session.get('user_id', 1)
        
        # 2. Base LEFT JOIN query for ALL questions
        base_query = '''
            SELECT tq.*, ur.user_answer, ur.is_correct, tq.explanation
            FROM test_questions tq
            LEFT JOIN user_responses ur ON tq.id = ur.question_id 
                AND ur.test_id = ? AND ur.user_id = ?
            WHERE tq.test_id = ?
        '''
        
        # 3. Filter by filter_type
        if filter_type == 'correct':
            where_clause = ' AND (ur.is_correct = 1 OR ur.is_correct IS NULL)'
        elif filter_type == 'incorrect':
            where_clause = ' AND ur.is_correct = 0'
        elif filter_type == 'all':
            where_clause = ''  # Show ALL questions
        else:
            abort(404, "Invalid filter")
        
        questions = conn.execute(base_query + where_clause, (test_id, user_id, test_id)).fetchall()
        print(f"DEBUG: Filter '{filter_type}' returned {len(questions)} questions")
        
        if not questions or q_index < 1 or q_index > len(questions):
            flash("No questions found for this filter")
            return redirect(url_for('test_bp.review_attempted', test_id=test_id))
        
        # 4. Current question + navigation
        question = questions[q_index - 1]
        prev_q = q_index - 1 if q_index > 1 else None
        next_q = q_index + 1 if q_index < len(questions) else None
        
        print(f"DEBUG: Showing question {question['id']}: user_answer={question['user_answer']}, is_correct={question['is_correct']}")
        
    finally:
        conn.close()
    
    return render_template('test/review_question.html',
                           test=test,
                           question=question,
                           q_index=q_index,
                           total=len(questions),
                           filter_type=filter_type,
                           prev_q=prev_q,
                           next_q=next_q)

@test_bp.route('/tests/<int:test_id>/submit', methods=['GET', 'POST'])
def submit_test(test_id):
    print(f"DEBUG SUBMIT: test_id={test_id}")
    
    if request.method == 'POST' and request.form.get('review') == 'review':
        print("DEBUG: Redirecting to review")
        return redirect(url_for('test_bp.review_attempted', test_id=test_id))
    
    # Find CORRECT DB for this test_id (4 lines only)
    # 🔥 USE SESSION DB (5 lines):
    db_file = session.get(f'test_{test_id}_db_file')
    if not db_file or not os.path.exists(db_file):
        flash("Test session expired!", "error")
        return redirect(url_for('test_bp.list_tests'))

    conn = dynamic_db_handler.get_connection(db_file)
    conn.row_factory = sqlite3.Row
    print(f"✅ SESSION DB: {os.path.basename(db_file)}")


         # 🔥 ADD DEBUG LOCATION (3 lines):
       


    try:
        # DEBUG: Check test exists
        test = conn.execute('SELECT * FROM test_info WHERE id = ?', (test_id,)).fetchone()
        print(f"DEBUG: Test found: {test['test_name'] if test else 'NOT FOUND'}")
        if not test:
            flash(f"Test ID {test_id} not found!")
            return redirect(url_for('test_bp.list_tests'))
        
        questions = conn.execute(
            'SELECT id, correct_answer FROM test_questions WHERE test_id = ? ORDER BY id',
            (test_id,)
        ).fetchall()
        print(f"DEBUG: Questions found: {len(questions)}")
        
        user_id = session.get('user_id', 1)
        answer_key = f'test_{test_id}_answers'
        answers = session.get(answer_key, {})
        print(f"DEBUG: Session answers: {answers}")
        
        for q in questions:
            qid = str(q['id'])
            user_answer = answers.get(qid)
            is_correct = 1 if user_answer and user_answer.upper() == q['correct_answer'].upper() else 0
            print(f"DEBUG Q{q['id']}: user='{user_answer}', correct='{q['correct_answer']}', score={is_correct}")
            
            conn.execute('''
                INSERT OR REPLACE INTO user_responses (test_id, user_id, question_id, user_answer, is_correct, test_started, test_submitted)
                VALUES (?, ?, ?, ?, ?, 1, 1)
            ''', (test_id, user_id, q['id'], user_answer, is_correct))
                    # Insert a durable completion marker (one row per user+test)

            questions = conn.execute(
            'SELECT id, correct_answer FROM test_questions WHERE test_id = ? ORDER BY id',
            (test_id,)
        ).fetchall()
        print(f"DEBUG: Questions found: {len(questions)}")

            # 🔥 ADD TABLE CREATION HERE:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                question_id INTEGER,
                user_answer TEXT,
                is_correct INTEGER,
                test_started INTEGER DEFAULT 0,
                test_submitted INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(test_id, user_id, question_id)
            )
        ''')
        conn.commit()
        print("DEBUG: user_responses table READY")
        # 🔥 END ADD
        try:
            conn.execute('''
                INSERT OR REPLACE INTO user_responses (test_id, user_id, question_id, test_submitted)
                VALUES (?, ?, 0, 1)
            ''', (test_id, user_id))
            print("✅ FALLBACK marker added")
        except:
            print("⚠️ Fallback marker skipped")
        
        conn.commit()
        print("DEBUG: Responses saved")

            
  

        conn.commit()


        print("DEBUG: Responses saved")
        
        total = len(questions)
        correct = sum(1 for q in questions if answers.get(str(q['id'])) 
                     and answers.get(str(q['id'])).upper() == q['correct_answer'].upper())
        wrong = sum(1 for q in questions if answers.get(str(q['id'])) 
                   and answers.get(str(q['id'])).upper() != q['correct_answer'].upper())
        unanswered = total - correct - wrong
        
    finally:
        conn.close()

    for key in [f'test_{test_id}_answers', f'test_{test_id}_marked', f'test_{test_id}_skipped']:
        session.pop(key, None)

    return render_template('test/report.html', test=test, total=total, correct=correct, wrong=wrong, unanswered=unanswered)

    
