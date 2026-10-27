import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "attendance.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _columns(conn, table):
    return [r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table)]


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                grade TEXT,
                section TEXT DEFAULT '',
                total_students INTEGER NOT NULL DEFAULT 0,
                mode TEXT NOT NULL,
                UNIQUE (teacher_id, name)
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                roll_no TEXT NOT NULL,
                name TEXT NOT NULL,
                embedding BLOB NOT NULL,
                UNIQUE (class_id, roll_no)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                class_name TEXT NOT NULL,
                subject TEXT,
                total_students INTEGER NOT NULL,
                session_date TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                present_count INTEGER DEFAULT 0,
                absent_count INTEGER DEFAULT 0,
                avg_engagement REAL
            );

            CREATE TABLE IF NOT EXISTS session_intervals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                time TEXT NOT NULL,
                avg_people REAL,
                engagement REAL,
                speaking_pct INTEGER,
                inactive_pct INTEGER
            );

            CREATE TABLE IF NOT EXISTS session_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                event TEXT NOT NULL,
                time TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS session_students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                student_id INTEGER,
                roll_no TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                first_seen TEXT
            );
        """)

        # upgrade databases created by earlier versions
        cols = _columns(conn, "classes")
        if "grade" not in cols:
            conn.execute("ALTER TABLE classes ADD COLUMN grade TEXT")
        if "section" not in cols:
            conn.execute("ALTER TABLE classes ADD COLUMN section TEXT DEFAULT ''")
        conn.execute("UPDATE classes SET grade = name WHERE grade IS NULL")
        conn.execute("UPDATE classes SET section = '' WHERE section IS NULL")


# ---------- teachers ----------

def create_teacher(name, email, password_hash):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO teachers (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, password_hash),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def get_teacher_by_email(email):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM teachers WHERE email = ?", (email,)
        ).fetchone()


# ---------- classes ----------

CLASS_SELECT = (
    "SELECT c.id, c.name, c.grade, COALESCE(c.section, '') AS section, c.mode, "
    "(SELECT COUNT(*) FROM students s WHERE s.class_id = c.id) AS strength "
    "FROM classes c "
)


def create_class(teacher_id, grade, section, mode):
    """Returns the new class id, or None if this teacher already has that class and section."""
    name = "%s-%s" % (grade, section) if section else grade
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO classes (teacher_id, name, grade, section, total_students, mode) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (teacher_id, name, grade, section, mode),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def list_classes(teacher_id):
    with get_conn() as conn:
        rows = conn.execute(
            CLASS_SELECT + "WHERE c.teacher_id = ? ORDER BY c.name", (teacher_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_class(teacher_id, class_id):
    with get_conn() as conn:
        row = conn.execute(
            CLASS_SELECT + "WHERE c.id = ? AND c.teacher_id = ?", (class_id, teacher_id)
        ).fetchone()
    return dict(row) if row else None


def update_class_mode(teacher_id, class_id, mode):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE classes SET mode = ? WHERE id = ? AND teacher_id = ?",
            (mode, class_id, teacher_id),
        )
        return cur.rowcount > 0


# ---------- students ----------

def add_student(class_id, roll_no, name, embedding_bytes):
    """Returns the new student id, or None if that roll number already exists in the class."""
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO students (class_id, roll_no, name, embedding) VALUES (?, ?, ?, ?)",
                (class_id, roll_no, name, embedding_bytes),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def list_students(class_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, roll_no, name FROM students WHERE class_id = ? "
            "ORDER BY LENGTH(roll_no), roll_no",
            (class_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_roster(class_id):
    """Students with their face fingerprints (embedding is raw bytes)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, roll_no, name, embedding FROM students WHERE class_id = ? "
            "ORDER BY LENGTH(roll_no), roll_no",
            (class_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_student(teacher_id, student_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT s.id FROM students s JOIN classes c ON c.id = s.class_id "
            "WHERE s.id = ? AND c.teacher_id = ?",
            (student_id, teacher_id),
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    return True


# ---------- sessions ----------

def todays_session(class_id):
    """The most recent session saved today for this class, or None."""
    today = time.strftime("%Y-%m-%d")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, session_date, started_at, present_count, absent_count, total_students "
            "FROM sessions WHERE class_id = ? AND session_date = ? "
            "ORDER BY started_at DESC LIMIT 1",
            (class_id, today),
        ).fetchone()
    return dict(row) if row else None


def save_session(teacher_id, info, started_at, ended_at, timeline, students):
    """students = one dict per roster student: student_id, roll_no, name, status, first_seen."""
    total = len(students)
    present = sum(1 for s in students if s["status"] == "present")
    absent = total - present

    scores = [r["engagement"] for r in timeline if r["engagement"] is not None]
    avg = round(sum(scores) / len(scores), 1) if scores else None

    fmt = "%Y-%m-%d %H:%M:%S"
    started = time.strftime(fmt, time.localtime(started_at))
    ended = time.strftime(fmt, time.localtime(ended_at))
    session_date = time.strftime("%Y-%m-%d", time.localtime(started_at))

    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO sessions
               (teacher_id, class_id, class_name, subject, total_students, session_date,
                started_at, ended_at, present_count, absent_count, avg_engagement)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (teacher_id, info["class_id"], info["class_name"], info.get("subject") or None,
             total, session_date, started, ended, present, absent, avg),
        )
        sid = cur.lastrowid
        conn.executemany(
            """INSERT INTO session_intervals
               (session_id, time, avg_people, engagement, speaking_pct, inactive_pct)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(sid, r["time"], r["avg_people"], r["engagement"],
              r["speaking_pct"], r["inactive_pct"]) for r in timeline],
        )
        conn.executemany(
            """INSERT INTO session_students
               (session_id, student_id, roll_no, name, status, first_seen)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(sid, s["student_id"], s["roll_no"], s["name"], s["status"], s["first_seen"])
             for s in students],
        )
    return sid


def list_sessions(teacher_id, date_from=None, date_to=None, class_id=None):
    query = (
        "SELECT id, session_date, class_name, subject, started_at, ended_at, "
        "total_students, present_count, absent_count, avg_engagement "
        "FROM sessions WHERE teacher_id = ?"
    )
    params = [teacher_id]
    if date_from:
        query += " AND session_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND session_date <= ?"
        params.append(date_to)
    if class_id:
        query += " AND class_id = ?"
        params.append(class_id)
    query += " ORDER BY started_at DESC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_session(teacher_id, session_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND teacher_id = ?",
            (session_id, teacher_id),
        ).fetchone()
    return dict(row) if row else None


def get_session_intervals(session_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT time, avg_people, engagement, speaking_pct, inactive_pct "
            "FROM session_intervals WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_session_students(session_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT roll_no, name, status, first_seen FROM session_students "
            "WHERE session_id = ? ORDER BY LENGTH(roll_no), roll_no",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_session(teacher_id, session_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE id = ? AND teacher_id = ?",
            (session_id, teacher_id),
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM session_intervals WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_events WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_students WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return True