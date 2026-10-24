from __future__ import annotations

import os
import re
import sqlite3
import sys

import pandas as pd

import config
from config import DB_CONFIG
from analysis import calculate_student_performance, assess_risk

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_DRIVER_AVAILABLE = True
except ImportError:
    MYSQL_DRIVER_AVAILABLE = False

    class MySQLError(Exception):
        pass

_CATCHABLE_DB_ERRORS = (MySQLError, sqlite3.Error)

class DatabaseError(Exception):

    pass

def _translate_mysql_schema_to_sqlite(mysql_schema: str) -> str:
    sql = mysql_schema
    sql = re.sub(r"CREATE DATABASE.*?;", "", sql, flags=re.S)
    sql = re.sub(r"USE .*?;", "", sql)
    sql = re.sub(r"INT AUTO_INCREMENT PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT", sql)
    sql = re.sub(r"ENGINE=InnoDB", "", sql)
    sql = re.sub(r"CHARACTER SET.*?;", ";", sql)
    sql = re.sub(r",\s*CONSTRAINT chk_marks_range CHECK \(marks >= 0 AND marks <= 100\)", "", sql)
    sql = re.sub(r"DECIMAL\(\d+,\d+\)", "REAL", sql)
    sql = re.sub(r"UNIQUE KEY \w+ \(([^)]+)\)", r"UNIQUE (\1)", sql)
    sql = re.sub(r"TIMESTAMP DEFAULT CURRENT_TIMESTAMP( ON UPDATE CURRENT_TIMESTAMP)?", "TEXT", sql)
    return sql

class _SQLiteCursor:
    def __init__(self, sqlite_conn, dictionary=False):
        self._cur = sqlite_conn.cursor()
        self.dictionary = dictionary
        self.lastrowid = None

    def execute(self, sql, params=None):
        sql = sql.replace("%s", "?")
        self._cur.execute(sql, params or [])
        self.lastrowid = self._cur.lastrowid

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        if self.dictionary:
            cols = [d[0] for d in self._cur.description]
            return dict(zip(cols, row))
        return row

    def fetchall(self):
        rows = self._cur.fetchall()
        if self.dictionary:
            cols = [d[0] for d in self._cur.description]
            return [dict(zip(cols, r)) for r in rows]
        return list(rows)

class SQLiteConnection:

    _initialized_paths = set()

    def __init__(self, path):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        if path not in SQLiteConnection._initialized_paths:
            self._ensure_schema()
            SQLiteConnection._initialized_paths.add(path)

    def _ensure_schema(self):
        cur = self._conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
        if cur.fetchone() is None:
            schema_path = os.path.join(config.BASE_DIR, "sql", "schema.sql")
            with open(schema_path) as f:
                self._conn.executescript(_translate_mysql_schema_to_sqlite(f.read()))
            self._conn.commit()

    def cursor(self, dictionary=False):
        return _SQLiteCursor(self._conn, dictionary=dictionary)

    def start_transaction(self):
        pass

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        pass

_warned_backend = False

def get_connection():

    global _warned_backend
    backend = config.DB_BACKEND

    def _warn(message):
        global _warned_backend
        if not _warned_backend:
            print(f"[database] {message}", file=sys.stderr)
            _warned_backend = True

    if backend == "sqlite":
        _warn("DB_BACKEND=sqlite -> using local SQLite fallback database "
              f"at {config.SQLITE_FALLBACK_PATH}. MySQL is not being used.")
        return SQLiteConnection(config.SQLITE_FALLBACK_PATH)

    if backend not in ("mysql", "auto"):
        raise DatabaseError(f"Unknown DB_BACKEND '{backend}'. Use 'mysql', 'sqlite', or 'auto'.")

    if not MYSQL_DRIVER_AVAILABLE:
        if backend == "mysql":
            raise DatabaseError(
                "DB_BACKEND=mysql but the 'mysql-connector-python' package is not installed. "
                "Run: pip install -r requirements.txt"
            )
        _warn("mysql-connector-python is not installed -> falling back to local SQLite database "
              f"at {config.SQLITE_FALLBACK_PATH}. Install mysql-connector-python and configure "
              "MySQL to use the real database (see README.md).")
        return SQLiteConnection(config.SQLITE_FALLBACK_PATH)

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if backend == "auto":
            _warn(f"Connected to MySQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}, "
                  f"database '{DB_CONFIG['database']}'.")
        return conn
    except _CATCHABLE_DB_ERRORS as e:
        if backend == "mysql":
            raise DatabaseError(
                f"Could not connect to MySQL ({DB_CONFIG['host']}:{DB_CONFIG['port']}, "
                f"database '{DB_CONFIG['database']}'). Details: {e}"
            ) from e
        _warn(f"Could not connect to MySQL ({e}) -> falling back to local SQLite database "
              f"at {config.SQLITE_FALLBACK_PATH}. Fix your MySQL setup (see README.md) to use "
              "the real database instead.")
        return SQLiteConnection(config.SQLITE_FALLBACK_PATH)

def active_backend() -> str:

    if config.DB_BACKEND == "sqlite":
        return "sqlite (forced)"
    if not MYSQL_DRIVER_AVAILABLE:
        return "sqlite (mysql-connector-python not installed)"
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.close()
        return "mysql"
    except _CATCHABLE_DB_ERRORS:
        if config.DB_BACKEND == "mysql":
            return "mysql (unreachable)"
        return "sqlite (mysql unreachable, using fallback)"

def has_active_dataset() -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM students")
        (count,) = cur.fetchone()
        return count > 0
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def import_dataset(cleaned_df: pd.DataFrame, subject_columns: list[str], filename: str) -> dict:

    conn = get_connection()
    try:
        conn.start_transaction()
        cur = conn.cursor()

        cur.execute("DELETE FROM student_performance")
        cur.execute("DELETE FROM student_marks")
        cur.execute("DELETE FROM students")
        cur.execute("DELETE FROM subjects")

        subject_id_by_name: dict[str, int] = {}
        for subject_name in subject_columns:
            cur.execute(
                "INSERT INTO subjects (subject_name) VALUES (%s)", (subject_name,)
            )
            subject_id_by_name[subject_name] = cur.lastrowid

        for _, row in cleaned_df.iterrows():
            cur.execute(
                "INSERT INTO students (student_id, student_name, branch, semester) "
                "VALUES (%s, %s, %s, %s)",
                (row["Student_ID"], row["Student_Name"], row["Branch"], int(row["Semester"])),
            )
            student_pk = cur.lastrowid

            marks_by_subject = {col: float(row[col]) for col in subject_columns}
            for subject_name, mark in marks_by_subject.items():
                cur.execute(
                    "INSERT INTO student_marks (student_id, subject_id, marks) VALUES (%s, %s, %s)",
                    (student_pk, subject_id_by_name[subject_name], mark),
                )

            perf = calculate_student_performance(marks_by_subject)
            risk = assess_risk(marks_by_subject, perf["overall_percentage"])
            cur.execute(
                "INSERT INTO student_performance "
                "(student_id, overall_percentage, performance_category, risk_level, risk_reasoning) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    student_pk,
                    perf["overall_percentage"],
                    perf["performance_category"],
                    risk["risk_level"],
                    risk["reasoning"],
                ),
            )

        cur.execute(
            "INSERT INTO uploads (filename, num_students, num_subjects) VALUES (%s, %s, %s)",
            (filename, len(cleaned_df), len(subject_columns)),
        )

        conn.commit()
        return {"num_students": len(cleaned_df), "num_subjects": len(subject_columns)}
    except _CATCHABLE_DB_ERRORS as e:
        conn.rollback()
        raise DatabaseError(f"Database import failed, no data was changed. Details: {e}") from e
    finally:
        conn.close()

def get_dashboard_stats() -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) AS total FROM students")
        total_students = cur.fetchone()["total"]

        if total_students == 0:
            return {
                "has_data": False,
                "total_students": 0,
                "class_average": 0,
                "excellent": 0,
                "good": 0,
                "average": 0,
                "at_risk": 0,
                "category_distribution": [],
            }

        cur.execute("SELECT AVG(overall_percentage) AS avg_pct FROM student_performance")
        class_average = float(cur.fetchone()["avg_pct"] or 0)

        cur.execute(
            "SELECT performance_category, COUNT(*) AS cnt "
            "FROM student_performance GROUP BY performance_category"
        )
        counts = {row["performance_category"]: row["cnt"] for row in cur.fetchall()}

        return {
            "has_data": True,
            "total_students": total_students,
            "class_average": round(class_average, 2),
            "excellent": counts.get("Excellent", 0),
            "good": counts.get("Good", 0),
            "average": counts.get("Average", 0),
            "at_risk": counts.get("At Risk", 0),
            "category_distribution": [
                {"category": k, "count": v} for k, v in counts.items()
            ],
        }
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def get_subject_overview() -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT s.subject_name, AVG(m.marks) AS avg_marks, "
            "MAX(m.marks) AS max_marks, MIN(m.marks) AS min_marks, COUNT(*) AS n "
            "FROM student_marks m JOIN subjects s ON m.subject_id = s.id "
            "GROUP BY s.id, s.subject_name ORDER BY s.subject_name"
        )
        rows = cur.fetchall()
        for r in rows:
            r["avg_marks"] = round(float(r["avg_marks"]), 2)
            r["max_marks"] = round(float(r["max_marks"]), 2)
            r["min_marks"] = round(float(r["min_marks"]), 2)
        return rows
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def list_subjects() -> list[str]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT subject_name FROM subjects ORDER BY subject_name")
        return [r[0] for r in cur.fetchall()]
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def get_subject_detail(subject_name: str) -> dict | None:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id FROM subjects WHERE subject_name = %s", (subject_name,))
        subj = cur.fetchone()
        if not subj:
            return None
        subject_id = subj["id"]

        cur.execute(
            "SELECT st.student_id, st.student_name, m.marks "
            "FROM student_marks m JOIN students st ON m.student_id = st.id "
            "WHERE m.subject_id = %s ORDER BY m.marks DESC",
            (subject_id,),
        )
        rows = cur.fetchall()
        marks = [float(r["marks"]) for r in rows]

        if not marks:
            return {
                "subject": subject_name, "average": 0, "highest": 0, "lowest": 0,
                "num_students": 0, "weak_students": [], "strong_students": [], "all_students": [],
            }

        weak = [r for r in rows if float(r["marks"]) < 40]
        strong = [r for r in rows if float(r["marks"]) >= 80]

        return {
            "subject": subject_name,
            "average": round(sum(marks) / len(marks), 2),
            "highest": max(marks),
            "lowest": min(marks),
            "num_students": len(marks),
            "weak_students": weak,
            "strong_students": strong,
            "all_students": rows,
        }
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def list_students() -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT st.student_id, st.student_name, st.branch, st.semester, "
            "p.overall_percentage, p.performance_category, p.risk_level "
            "FROM students st LEFT JOIN student_performance p ON p.student_id = st.id "
            "ORDER BY st.student_name"
        )
        return cur.fetchall()
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def get_student_detail(student_id: str) -> dict | None:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, student_id, student_name, branch, semester FROM students WHERE student_id = %s",
            (student_id,),
        )
        student = cur.fetchone()
        if not student:
            return None

        cur.execute(
            "SELECT s.subject_name, m.marks FROM student_marks m "
            "JOIN subjects s ON m.subject_id = s.id WHERE m.student_id = %s "
            "ORDER BY s.subject_name",
            (student["id"],),
        )
        marks = cur.fetchall()

        cur.execute(
            "SELECT overall_percentage, performance_category, risk_level, risk_reasoning "
            "FROM student_performance WHERE student_id = %s",
            (student["id"],),
        )
        perf = cur.fetchone() or {}

        return {
            "student_id": student["student_id"],
            "student_name": student["student_name"],
            "branch": student["branch"],
            "semester": student["semester"],
            "marks": marks,
            "overall_percentage": float(perf.get("overall_percentage", 0)),
            "performance_category": perf.get("performance_category", "N/A"),
            "risk_level": perf.get("risk_level", "N/A"),
            "risk_reasoning": perf.get("risk_reasoning", ""),
        }
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def get_top_students(limit: int = 5) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT st.student_id, st.student_name, p.overall_percentage "
            "FROM student_performance p JOIN students st ON p.student_id = st.id "
            "ORDER BY p.overall_percentage DESC LIMIT %s",
            (limit,),
        )
        return cur.fetchall()
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def get_students_needing_attention(limit: int = 5) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT st.student_id, st.student_name, p.overall_percentage, p.risk_level "
            "FROM student_performance p JOIN students st ON p.student_id = st.id "
            "ORDER BY p.overall_percentage ASC LIMIT %s",
            (limit,),
        )
        return cur.fetchall()
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()

def get_last_upload_info() -> dict | None:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT filename, num_students, num_subjects, uploaded_at "
            "FROM uploads ORDER BY id DESC LIMIT 1"
        )
        return cur.fetchone()
    except _CATCHABLE_DB_ERRORS as e:
        raise DatabaseError(str(e)) from e
    finally:
        conn.close()
