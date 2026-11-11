import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "school.db"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('teacher','student')),
            class_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(teacher_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            instructions TEXT DEFAULT '',
            questions TEXT NOT NULL,
            published INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(teacher_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            answers TEXT NOT NULL,
            score REAL NOT NULL,
            total REAL NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(test_id, student_id),
            FOREIGN KEY(test_id) REFERENCES tests(id),
            FOREIGN KEY(student_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS learning_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            details TEXT DEFAULT '',
            FOREIGN KEY(teacher_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS task_progress (
            task_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'To learn',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(task_id, student_id),
            FOREIGN KEY(task_id) REFERENCES learning_tasks(id),
            FOREIGN KEY(student_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS answer_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            question TEXT NOT NULL,
            marks REAL NOT NULL,
            max_marks REAL NOT NULL,
            feedback TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(teacher_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_materials_teacher ON materials(teacher_id);
        CREATE INDEX IF NOT EXISTS idx_tests_teacher ON tests(teacher_id);
        CREATE INDEX IF NOT EXISTS idx_results_student ON test_results(student_id);
        """)
        # A teacher receives a class code at registration. This migration supports
        # databases created by earlier versions of this app.
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "class_code" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN class_code TEXT")


def create_user(name, email, password_hash, salt, role, class_code=None):
    with connect() as conn:
        conn.execute(
            "INSERT INTO users(name,email,password_hash,salt,role,class_code) VALUES(?,?,?,?,?,?)",
            (name, email, password_hash, salt, role, class_code)
        )


def get_user_by_email(email):
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_teacher_by_code(code):
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE role='teacher' AND class_code=?",
            (code.upper(),)
        ).fetchone()
        return dict(row) if row else None


def get_teacher_students(teacher_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id,name,email FROM users WHERE role='student' AND class_code = "
            "(SELECT class_code FROM users WHERE id=?) ORDER BY name",
            (teacher_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def add_material(teacher_id, filename, content):
    with connect() as conn:
        conn.execute(
            "INSERT INTO materials(teacher_id,filename,content) VALUES(?,?,?)",
            (teacher_id, filename, content)
        )


def get_materials(teacher_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id,filename,content,created_at FROM materials WHERE teacher_id=? ORDER BY id DESC",
            (teacher_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_material(material_id, teacher_id):
    with connect() as conn:
        conn.execute("DELETE FROM materials WHERE id=? AND teacher_id=?", (material_id, teacher_id))


def add_test(teacher_id, title, subject, instructions, questions, published=True):
    import json
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tests(teacher_id,title,subject,instructions,questions,published) VALUES(?,?,?,?,?,?)",
            (teacher_id, title, subject, instructions, json.dumps(questions), int(published))
        )
        return cur.lastrowid


def get_teacher_tests(teacher_id):
    import json
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tests WHERE teacher_id=? ORDER BY id DESC", (teacher_id,)
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["questions"] = json.loads(item["questions"])
            result.append(item)
        return result


def get_student_tests(class_code):
    import json
    with connect() as conn:
        rows = conn.execute(
            "SELECT t.* FROM tests t JOIN users u ON u.id=t.teacher_id "
            "WHERE u.class_code=? AND t.published=1 ORDER BY t.id DESC",
            (class_code,)
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["questions"] = json.loads(item["questions"])
            result.append(item)
        return result


def save_test_result(test_id, student_id, answers, score, total):
    import json
    with connect() as conn:
        conn.execute(
            "INSERT INTO test_results(test_id,student_id,answers,score,total) VALUES(?,?,?,?,?) "
            "ON CONFLICT(test_id,student_id) DO UPDATE SET answers=excluded.answers, "
            "score=excluded.score,total=excluded.total,submitted_at=CURRENT_TIMESTAMP",
            (test_id, student_id, json.dumps(answers), score, total)
        )


def student_has_attempted(test_id, student_id):
    with connect() as conn:
        return conn.execute(
            "SELECT 1 FROM test_results WHERE test_id=? AND student_id=?",
            (test_id, student_id)
        ).fetchone() is not None


def get_teacher_results(teacher_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT u.name AS student, t.title AS test, r.score, r.total, "
            "ROUND(100.0*r.score/NULLIF(r.total,0),1) AS percentage, r.submitted_at "
            "FROM test_results r JOIN tests t ON t.id=r.test_id "
            "JOIN users u ON u.id=r.student_id WHERE t.teacher_id=? "
            "ORDER BY r.submitted_at DESC",
            (teacher_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_student_results(student_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT t.title AS test, t.subject, r.score, r.total, "
            "ROUND(100.0*r.score/NULLIF(r.total,0),1) AS percentage, r.submitted_at "
            "FROM test_results r JOIN tests t ON t.id=r.test_id "
            "WHERE r.student_id=? ORDER BY r.submitted_at DESC",
            (student_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def add_learning_task(teacher_id, title, subject, details):
    with connect() as conn:
        conn.execute(
            "INSERT INTO learning_tasks(teacher_id,title,subject,details) VALUES(?,?,?,?)",
            (teacher_id, title, subject, details)
        )


def get_student_tasks(class_code, student_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT t.*, COALESCE(p.status,'To learn') AS status "
            "FROM learning_tasks t JOIN users u ON u.id=t.teacher_id "
            "LEFT JOIN task_progress p ON p.task_id=t.id AND p.student_id=? "
            "WHERE u.class_code=? ORDER BY t.id DESC",
            (student_id, class_code)
        ).fetchall()
        return [dict(r) for r in rows]


def set_task_status(task_id, student_id, status):
    with connect() as conn:
        conn.execute(
            "INSERT INTO task_progress(task_id,student_id,status) VALUES(?,?,?) "
            "ON CONFLICT(task_id,student_id) DO UPDATE SET status=excluded.status, "
            "updated_at=CURRENT_TIMESTAMP",
            (task_id, student_id, status)
        )


def save_answer_check(teacher_id, student_name, question, marks, max_marks, feedback):
    with connect() as conn:
        conn.execute(
            "INSERT INTO answer_checks(teacher_id,student_name,question,marks,max_marks,feedback) "
            "VALUES(?,?,?,?,?,?)",
            (teacher_id, student_name, question, marks, max_marks, feedback)
        )


def get_dashboard_stats(teacher_id):
    with connect() as conn:
        students = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='student' AND class_code="
            "(SELECT class_code FROM users WHERE id=?)", (teacher_id,)
        ).fetchone()[0]
        tests = conn.execute("SELECT COUNT(*) FROM tests WHERE teacher_id=?", (teacher_id,)).fetchone()[0]
        attempts = conn.execute(
            "SELECT COUNT(*) FROM test_results r JOIN tests t ON t.id=r.test_id WHERE t.teacher_id=?",
            (teacher_id,)
        ).fetchone()[0]
        avg = conn.execute(
            "SELECT AVG(100.0*r.score/NULLIF(r.total,0)) FROM test_results r "
            "JOIN tests t ON t.id=r.test_id WHERE t.teacher_id=?", (teacher_id,)
        ).fetchone()[0]
        checks = conn.execute("SELECT COUNT(*) FROM answer_checks WHERE teacher_id=?", (teacher_id,)).fetchone()[0]
        return {"students": students, "tests": tests, "attempts": attempts,
                "average": round(avg or 0, 1), "checks": checks}
