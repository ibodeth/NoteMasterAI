import sqlite3
import os
from datetime import datetime

def init_db(db_path):
    """
    Initializes the SQLite database with required tables.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Students Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        student_number TEXT,
        class_name TEXT,
        unit_path TEXT,
        total_score REAL DEFAULT 0.0,
        max_score REAL DEFAULT 100.0,
        teacher_note TEXT DEFAULT "",
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Zone Results Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS zone_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        question_name TEXT,
        question_type TEXT,
        score REAL,
        max_points REAL,
        student_text TEXT,
        correct_answer TEXT,
        ai_reason TEXT,
        crop_path TEXT,
        teacher_correction REAL DEFAULT NULL,
        teacher_note TEXT DEFAULT "",
        FOREIGN KEY(student_id) REFERENCES students(id)
    )
    ''')
    
    # MIGRATION: Ensure new columns exist
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN student_number TEXT")
    except sqlite3.OperationalError:
        pass # Already exists
        
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN class_name TEXT")
    except sqlite3.OperationalError:
        pass # Already exists
        
    try:
        cursor.execute("ALTER TABLE zone_results ADD COLUMN correct_answer TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE zone_results ADD COLUMN key_crop_path TEXT")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

def save_student_header(db_path, name, unit_path, student_number="", class_name=""):
    """
    Creates a new student record and returns the student_id.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO students (name, unit_path, student_number, class_name, created_at) 
    VALUES (?, ?, ?, ?, ?)
    ''', (name, unit_path, student_number, class_name, datetime.now()))
    
    student_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return student_id

def update_student_score(db_path, student_id, total_score):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('UPDATE students SET total_score = ? WHERE id = ?', (total_score, student_id))
    conn.commit()
    conn.close()

def save_zone_result(db_path, student_id, z_res):
    """
    z_res dict expected:
    {
        "name": "Soru 1",
        "type": "Klasik",
        "score": 5.0,
        "max_points": 10.0, # Need to pass this
        "student_text": "...",
        "details": "...", # effectively ai_reason
        "crop_path": "..."
    }
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO zone_results (
        student_id, question_name, question_type, score, max_points, 
        student_text, correct_answer, ai_reason, crop_path, key_crop_path
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        student_id, 
        z_res.get("name"), 
        z_res.get("type"), 
        z_res.get("score", 0.0), 
        z_res.get("max_points", 0.0), # Ensure we add this to z_res
        z_res.get("student_text", ""), 
        z_res.get("correct_answer", ""), # NEW
        z_res.get("reason", ""), # Use reason raw string
        z_res.get("crop_path", ""),
        z_res.get("key_crop_path", "") # NEW
    ))
    
    conn.commit()
    conn.close()

def get_all_results(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM students ORDER BY id DESC')
    students = [dict(row) for row in cursor.fetchall()]
    
    for s in students:
        cursor.execute('SELECT * FROM zone_results WHERE student_id = ?', (s['id'],))
        s['results'] = [dict(row) for row in cursor.fetchall()]
        
    conn.close()
    return students

def update_zone_score(db_path, zone_id, new_score, teacher_note=""):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE zone_results 
        SET teacher_correction = ?, teacher_note = ?
        WHERE id = ?
    """, (new_score, teacher_note, zone_id))
    conn.commit()
    conn.close()

def recalculate_student_total(db_path, student_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Sum all zone scores for this student. Use teacher_correction if available, else score.
    # Actually update_zone_score sets both score and teacher_correction to be safe for now, 
    # or we prefer logic: score = original AI, teacher_correction = override.
    # Let's check update_zone_score above: I set both. 
    # Better logic: Keep 'score' as AI score (history), set 'teacher_correction'.
    # But for simplicity of "total_score" sum, if we just sum 'score' column, we lose history?
    # Schema says: score REAL, teacher_correction REAL.
    # Let's adjust update_zone_score to ONLY set teacher_correction.
    
    # RE-READING my previous attempt's thought process: I wanted to update 'teacher_correction'.
    # But wait, the list view shows 'total_score' from students table.
    
    cursor.execute("""
        SELECT SUM(COALESCE(teacher_correction, score)) 
        FROM zone_results 
        WHERE student_id = ?
    """, (student_id,))
    
    total = cursor.fetchone()[0] or 0.0
    
    # Update student table
    cursor.execute("UPDATE students SET total_score = ? WHERE id = ?", (total, student_id))
    conn.commit()
    conn.close()
    return total

def update_student_metadata(db_path, student_id, name, number, class_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE students 
        SET name = ?, student_number = ?, class_name = ?
        WHERE id = ?
    """, (name, number, class_name, student_id))
    conn.commit()
    conn.close()
