import io
import os
import re
import sqlite3
import sys
import types
import unittest

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, BACKEND)

mysql_pkg = types.ModuleType("mysql")
connector_mod = types.ModuleType("mysql.connector")

class _StubError(Exception):
    pass

connector_mod.Error = _StubError
connector_mod.connect = lambda **kwargs: None
mysql_pkg.connector = connector_mod
sys.modules["mysql"] = mysql_pkg
sys.modules["mysql.connector"] = connector_mod

import database

class FakeCursor:
    def __init__(self, conn, dictionary=False):
        self._cur = conn.cursor()
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

_SHARED_SQLITE_CONN = sqlite3.connect(":memory:", check_same_thread=False)
_SHARED_SQLITE_CONN.execute("PRAGMA foreign_keys = ON")
schema_path = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")
with open(schema_path) as f:
    _SHARED_SQLITE_CONN.executescript(translate_schema_to_sqlite(f.read()))
_SHARED_SQLITE_CONN.commit()

database.get_connection = lambda: FakeConnection(_SHARED_SQLITE_CONN)

import app as flask_app_module

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_data")

def load(name):
    with open(os.path.join(SAMPLE_DIR, name), "rb") as f:
        return f.read()

class TestFlaskHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        flask_app_module.app.testing = True
        cls.client = flask_app_module.app.test_client()

    def test_01_pages_render_before_any_upload(self):
        for path in ["/", "/upload", "/subjects", "/prediction", "/reports"]:
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, f"{path} failed")

    def test_02_dashboard_api_empty_state(self):
        resp = self.client.get("/api/dashboard")
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertFalse(data["has_data"])

    def test_03_upload_invalid_csv_rejected_via_real_http_multipart(self):
        csv_bytes = load("invalid_sample.csv")
        resp = self.client.post(
            "/api/upload",
            data={"csv_file": (io.BytesIO(csv_bytes), "invalid_sample.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data["success"])
        self.assertTrue(any("Row 3, DBMS" in m for m in data["validation_errors"]))
        self.assertTrue(any("more than once" in m for m in data["validation_errors"]))

        resp = self.client.get("/api/dashboard")
        self.assertFalse(resp.get_json()["has_data"])

    def test_04_upload_valid_csv_via_real_http_multipart(self):
        csv_bytes = load("sample_students.csv")
        resp = self.client.post(
            "/api/upload",
            data={"csv_file": (io.BytesIO(csv_bytes), "sample_students.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["num_students"], 10)
        self.assertEqual(data["num_subjects"], 5)
        self.assertIn("Successfully imported 10 students and 5 subjects", data["message"])

    def test_05_dashboard_reflects_uploaded_data(self):
        resp = self.client.get("/api/dashboard")
        data = resp.get_json()
        self.assertTrue(data["has_data"])
        self.assertEqual(data["total_students"], 10)
        self.assertEqual(len(data["subject_overview"]), 5)

    def test_06_subjects_api(self):
        resp = self.client.get("/api/subjects")
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["subjects"]), 5)

    def test_07_students_api_and_detail_page(self):
        resp = self.client.get("/api/students")
        data = resp.get_json()
        self.assertEqual(len(data["students"]), 10)

        resp = self.client.get("/api/students/STU001")
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["student"]["student_name"], "Aarav Mehta")

        resp = self.client.get("/student/STU001")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/api/students/NOPE")
        self.assertEqual(resp.status_code, 404)

    def test_08_prediction_api(self):
        resp = self.client.get("/api/prediction/STU006")
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn(data["prediction"]["risk_level"], ("High Risk", "Moderate Risk"))
        self.assertNotIn("accuracy", data["note"].lower().replace("no historical outcome label to train on.", ""))

        resp = self.client.get("/api/prediction")
        data = resp.get_json()
        self.assertEqual(len(data["predictions"]), 10)

    def test_09_reports_api(self):
        resp = self.client.get("/api/reports")
        data = resp.get_json()
        self.assertTrue(data["has_data"])
        self.assertEqual(len(data["top_students"]), 5)
        self.assertEqual(len(data["students_needing_attention"]), 5)

    def test_10_sample_csv_download(self):
        resp = self.client.get("/api/sample-csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Student_ID", resp.get_data(as_text=True))

    def test_11_second_upload_replaces_dataset(self):
        csv_bytes = load("sample_students_different_subjects.csv")
        resp = self.client.post(
            "/api/upload",
            data={"csv_file": (io.BytesIO(csv_bytes), "sample_students_different_subjects.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["num_students"], 4)

        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.get_json()["total_students"], 4)
        resp = self.client.get("/api/students/STU001")
        self.assertEqual(resp.status_code, 404)

    def test_12_non_csv_file_rejected(self):
        resp = self.client.post(
            "/api/upload",
            data={"csv_file": (io.BytesIO(b"not a csv"), "data.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["success"])

    def test_13_empty_file_rejected(self):
        resp = self.client.post(
            "/api/upload",
            data={"csv_file": (io.BytesIO(b""), "empty.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["success"])

    def test_14_no_file_in_request_rejected(self):
        resp = self.client.post("/api/upload", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["success"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
