import sqlite3

def get_test_schema():
    """Schema for test-type databases with subjects, topics, MCQs, and timing info"""
    return {
        'test_info': '''
            CREATE TABLE IF NOT EXISTS test_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER NOT NULL,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''',
        'test_questions': '''
            CREATE TABLE IF NOT EXISTS test_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer TEXT NOT NULL, -- one of 'a', 'b', 'c', 'd'
                FOREIGN KEY (test_id) REFERENCES test_info (id)
            )
        ''',
        'test_results': '''
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                user_id INTEGER,
                score INTEGER,
                taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_id) REFERENCES test_info (id)
            )
        '''
    }

def create_test_tables(db_file='test_database.db'):
    schema = get_test_schema()
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    try:
        for table_name, create_sql in schema.items():
            print(f"Creating or verifying table '{table_name}'...")
            cursor.execute(create_sql)
        conn.commit()
        print(f"All tables created or verified successfully in '{db_file}'.")
    except sqlite3.Error as e:
        print(f"SQLite error occurred: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    create_test_tables()
