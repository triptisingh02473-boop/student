import io
import os
import sys
import tempfile
import unittest

BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, BACKEND)

import config

class TestBackendFallback(unittest.TestCase):
    def setUp(self):

        self.tmp_dir = tempfile.mkdtemp()
        self.sqlite_path = os.path.join(self.tmp_dir, "test_fallback.db")
        config.SQLITE_FALLBACK_PATH = self.sqlite_path
        config.DB_BACKEND = "auto"

        for mod in ("database",):
            sys.modules.pop(mod, None)
        global database
        import database

    def test_auto_falls_back_to_sqlite_when_driver_missing(self):

        if database.MYSQL_DRIVER_AVAILABLE:
            self.skipTest("mysql-connector-python is installed in this environment; "
                           "fallback-on-missing-driver path can't be exercised here.")

        config.DB_BACKEND = "auto"
        conn = database.get_connection()
        self.assertIsInstance(conn, database.SQLiteConnection)
        conn.close()

        self.assertIn("sqlite", database.active_backend())

    def test_forced_sqlite_backend(self):
        config.DB_BACKEND = "sqlite"
        conn = database.get_connection()
        self.assertIsInstance(conn, database.SQLiteConnection)
        self.assertTrue(os.path.exists(self.sqlite_path))
        conn.close()

    def test_forced_mysql_backend_raises_clear_error_when_driver_missing(self):
        if database.MYSQL_DRIVER_AVAILABLE:
            self.skipTest("mysql-connector-python is installed in this environment.")
        config.DB_BACKEND = "mysql"
        with self.assertRaises(database.DatabaseError) as ctx:
            database.get_connection()
        self.assertIn("mysql-connector-python", str(ctx.exception))

    def test_fallback_schema_matches_real_schema_tables(self):
        config.DB_BACKEND = "sqlite"
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cur.fetchall()}
        expected = {"students", "subjects", "student_marks", "student_performance", "uploads"}
        self.assertTrue(expected.issubset(tables), tables)
        conn.close()

    def test_full_upload_cycle_on_forced_sqlite_backend(self):
        import pandas as pd
        from analysis import validate_csv

        config.DB_BACKEND = "sqlite"

        sample_path = os.path.join(os.path.dirname(__file__), "..", "sample_data", "sample_students.csv")
        with open(sample_path, "rb") as f:
            df = pd.read_csv(io.BytesIO(f.read()))
        result = validate_csv(df)
        self.assertTrue(result.is_valid)

        import_result = database.import_dataset(result.cleaned_df, result.subject_columns, "sample_students.csv")
        self.assertEqual(import_result["num_students"], 10)

        stats = database.get_dashboard_stats()
        self.assertTrue(stats["has_data"])
        self.assertEqual(stats["total_students"], 10)

if __name__ == "__main__":
    unittest.main(verbosity=2)
