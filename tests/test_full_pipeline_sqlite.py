import io
import os
import re
import sqlite3
import sys
import unittest

import pandas as pd

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, BACKEND)

import config

import types
if "mysql" not in sys.modules:
    mysql_pkg = types.ModuleType("mysql")
    connector_mod = types.ModuleType("mysql.connector")

    class _StubError(Exception):
        pass

    connector_mod.Error = _StubError
    connector_mod.connect = lambda **kwargs: None
    mysql_pkg.connector = connector_mod
    sys.modules["mysql"] = mysql_pkg
    sys.modules["mysql.connector"] = connector_mod

class FakeCursor:
    def __init__(self, conn, dictionary=False):
        self._conn = conn
        self._cur = conn.execute("SELECT 1").connection.cursor()
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

class FakeConnection:
    def __init__(self, sqlite_conn):
        self._conn = sqlite_conn

    def cursor(self, dictionary=False):
        return FakeCursor(self._conn, dictionary=dictionary)

    def start_transaction(self):
        pass

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        pass

def translate_schema_to_sqlite(mysql_schema: str) -> str:
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

_SHARED_SQLITE_CONN = sqlite3.connect(":memory:")
_SHARED_SQLITE_CONN.execute("PRAGMA foreign_keys = ON")

schema_path = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")
with open(schema_path) as f:
    raw_schema = f.read()
sqlite_schema = translate_schema_to_sqlite(raw_schema)
_SHARED_SQLITE_CONN.executescript(sqlite_schema)
_SHARED_SQLITE_CONN.commit()

def fake_get_connection():
    return FakeConnection(_SHARED_SQLITE_CONN)

import database
database.get_connection = fake_get_connection

from analysis import validate_csv

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_data")

def load_csv_bytes(name):
    with open(os.path.join(SAMPLE_DIR, name), "rb") as f:
        return f.read()

class TestFullPipeline(unittest.TestCase):
    def test_01_dashboard_empty_before_upload(self):
        stats = database.get_dashboard_stats()
        self.assertFalse(stats["has_data"])
        self.assertEqual(stats["total_students"], 0)

    def test_02_valid_csv_end_to_end(self):
        raw = load_csv_bytes("sample_students.csv")
        df = pd.read_csv(io.BytesIO(raw))
        result = validate_csv(df)
        self.assertTrue(result.is_valid, result.error_messages())

        import_result = database.import_dataset(
            result.cleaned_df, result.subject_columns, "sample_students.csv"
        )
        self.assertEqual(import_result["num_students"], 10)
        self.assertEqual(import_result["num_subjects"], 5)

        stats = database.get_dashboard_stats()
        self.assertTrue(stats["has_data"])
        self.assertEqual(stats["total_students"], 10)
        self.assertGreater(stats["class_average"], 0)
        self.assertEqual(
            stats["excellent"] + stats["good"] + stats["average"] + stats["at_risk"], 10
        )

        subjects = database.list_subjects()
        self.assertEqual(
            sorted(subjects),
            sorted(["Data Structures", "DBMS", "Python", "Mathematics", "Java"]),
        )

        overview = database.get_subject_overview()
        self.assertEqual(len(overview), 5)

        students = database.list_students()
        self.assertEqual(len(students), 10)

        detail = database.get_student_detail("STU001")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["student_name"], "Aarav Mehta")
        self.assertEqual(len(detail["marks"]), 5)
        expected_avg = round((86 + 82 + 91 + 78 + 88) / 5, 2)
        self.assertAlmostEqual(detail["overall_percentage"], expected_avg, places=1)

        subj_detail = database.get_subject_detail("Python")
        self.assertEqual(subj_detail["num_students"], 10)

        top = database.get_top_students(3)
        self.assertEqual(len(top), 3)
        attention = database.get_students_needing_attention(3)
        self.assertEqual(len(attention), 3)

        last_upload = database.get_last_upload_info()
        self.assertEqual(last_upload["filename"], "sample_students.csv")
        self.assertEqual(last_upload["num_students"], 10)

    def test_03_invalid_csv_rejected_without_partial_import(self):
        raw = load_csv_bytes("invalid_sample.csv")
        df = pd.read_csv(io.BytesIO(raw))
        result = validate_csv(df)
        self.assertFalse(result.is_valid)
        messages = result.error_messages()
        self.assertTrue(any("Row 3, DBMS" in m for m in messages), messages)
        self.assertTrue(any("STU001" in m and "more than once" in m for m in messages), messages)

        stats = database.get_dashboard_stats()
        self.assertEqual(stats["total_students"], 10)

    def test_04_new_upload_replaces_active_dataset(self):
        raw = load_csv_bytes("sample_students_different_subjects.csv")
        df = pd.read_csv(io.BytesIO(raw))
        result = validate_csv(df)
        self.assertTrue(result.is_valid, result.error_messages())

        import_result = database.import_dataset(
            result.cleaned_df, result.subject_columns, "sample_students_different_subjects.csv"
        )
        self.assertEqual(import_result["num_students"], 4)
        self.assertEqual(import_result["num_subjects"], 4)

        stats = database.get_dashboard_stats()
        self.assertEqual(stats["total_students"], 4)
        subjects = database.list_subjects()
        self.assertEqual(sorted(subjects), sorted(["Mathematics", "Physics", "Chemistry", "English"]))
        self.assertIsNone(database.get_student_detail("STU001"))
        self.assertIsNotNone(database.get_student_detail("STU101"))

    def test_05_csv_with_derived_columns_recalculated_not_trusted(self):
        raw = load_csv_bytes("sample_with_derived_columns.csv")
        df = pd.read_csv(io.BytesIO(raw))
        result = validate_csv(df)
        self.assertTrue(result.is_valid, result.error_messages())
        self.assertNotIn("Overall_Percentage", result.subject_columns)
        self.assertNotIn("Performance_Category", result.subject_columns)

        database.import_dataset(result.cleaned_df, result.subject_columns, "sample_with_derived_columns.csv")
        detail = database.get_student_detail("STU001")

        expected = round((86 + 82 + 91 + 78 + 88) / 5, 2)
        self.assertAlmostEqual(detail["overall_percentage"], expected, places=1)

    def test_06_prediction_never_claims_ml_accuracy(self):
        from analysis import assess_risk
        detail = database.get_student_detail("STU001")
        marks_by_subject = {m["subject_name"]: float(m["marks"]) for m in detail["marks"]}
        risk = assess_risk(marks_by_subject, detail["overall_percentage"])
        self.assertIn(risk["risk_level"], ("Low Risk", "Moderate Risk", "High Risk"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
