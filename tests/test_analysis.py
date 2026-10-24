import io
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import analysis

VALID_CSV = """Student_ID,Student_Name,Branch,Semester,Data Structures,DBMS,Python,Mathematics,Java
STU001,Aarav Mehta,CSE,3,86,82,91,78,88
STU002,Diya Sharma,CSE,3,74,79,81,72,76
STU003,Kabir Rao,CSE,3,62,68,65,59,64
"""

DIFFERENT_SUBJECTS_CSV = """Student_ID,Student_Name,Branch,Semester,Mathematics,Physics,Chemistry,English
STU010,Neha Iyer,ECE,2,45,50,39,60
STU011,Rohan Das,ECE,2,90,85,92,88
"""

CSV_WITH_DERIVED_COLUMNS = """Student_ID,Student_Name,Branch,Semester,Data Structures,DBMS,Python,Mathematics,Java,Overall_Percentage,Performance_Category
STU001,Aarav Mehta,CSE,3,86,82,91,78,88,85,Excellent
STU002,Diya Sharma,CSE,3,74,79,81,72,76,76.4,Good
"""

INVALID_MARK_CSV = """Student_ID,Student_Name,Branch,Semester,Data Structures,DBMS,Python,Mathematics,Java
STU001,Aarav Mehta,CSE,3,86,82,91,78,88
STU002,Diya Sharma,CSE,3,74,150,81,72,76
STU003,,CSE,3,62,68,65,59,64
"""

DUPLICATE_ID_CSV = """Student_ID,Student_Name,Branch,Semester,Python,Java
STU001,Aarav Mehta,CSE,3,80,85
STU001,Someone Else,CSE,3,60,65
"""

EMPTY_ROWS_CSV = """Student_ID,Student_Name,Branch,Semester,Python,Java
STU001,Aarav Mehta,CSE,3,80,85
,,,,,
STU002,Diya Sharma,CSE,3,90,88
"""

MISSING_REQUIRED_COL_CSV = """Student_ID,Student_Name,Semester,Python,Java
STU001,Aarav Mehta,3,80,85
"""

NO_SUBJECT_COLUMNS_CSV = """Student_ID,Student_Name,Branch,Semester
STU001,Aarav Mehta,CSE,3
"""

def read(csv_text: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(csv_text))

class TestSubjectDetection(unittest.TestCase):
    def test_detects_five_subjects(self):
        df = read(VALID_CSV)
        cols = analysis.detect_subject_columns(df)
        self.assertEqual(
            cols, ["Data Structures", "DBMS", "Python", "Mathematics", "Java"]
        )

    def test_detects_different_subject_names(self):
        df = read(DIFFERENT_SUBJECTS_CSV)
        cols = analysis.detect_subject_columns(df)
        self.assertEqual(cols, ["Mathematics", "Physics", "Chemistry", "English"])

    def test_ignores_derived_columns(self):
        df = read(CSV_WITH_DERIVED_COLUMNS)
        cols = analysis.detect_subject_columns(df)
        self.assertNotIn("Overall_Percentage", cols)
        self.assertNotIn("Performance_Category", cols)
        self.assertEqual(
            cols, ["Data Structures", "DBMS", "Python", "Mathematics", "Java"]
        )

class TestValidation(unittest.TestCase):
    def test_valid_csv_passes(self):
        df = read(VALID_CSV)
        result = analysis.validate_csv(df)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(
            result.subject_columns,
            ["Data Structures", "DBMS", "Python", "Mathematics", "Java"],
        )
        self.assertEqual(len(result.cleaned_df), 3)

    def test_csv_with_derived_columns_still_valid_and_ignores_them(self):
        df = read(CSV_WITH_DERIVED_COLUMNS)
        result = analysis.validate_csv(df)
        self.assertTrue(result.is_valid)
        self.assertNotIn("Overall_Percentage", result.subject_columns)
        self.assertNotIn("Performance_Category", result.subject_columns)
        self.assertTrue(any("recalculated" in w for w in result.warnings))

    def test_invalid_mark_out_of_range_reported_precisely(self):
        df = read(INVALID_MARK_CSV)
        result = analysis.validate_csv(df)
        self.assertFalse(result.is_valid)
        messages = result.error_messages()

        self.assertTrue(any("Row 3, DBMS" in m for m in messages), messages)
        self.assertTrue(any("must be a number between 0 and 100" in m for m in messages), messages)

        self.assertFalse(any("Performance_Category" in m for m in messages), messages)

    def test_missing_name_reported(self):
        df = read(INVALID_MARK_CSV)
        result = analysis.validate_csv(df)
        messages = result.error_messages()
        self.assertTrue(any("Student_Name" in m and "cannot be empty" in m for m in messages), messages)

    def test_no_partial_import_on_failure(self):
        df = read(INVALID_MARK_CSV)
        result = analysis.validate_csv(df)
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.cleaned_df)

    def test_duplicate_student_id_detected(self):
        df = read(DUPLICATE_ID_CSV)
        result = analysis.validate_csv(df)
        self.assertFalse(result.is_valid)
        messages = result.error_messages()
        self.assertTrue(any("STU001" in m and "more than once" in m for m in messages), messages)

    def test_empty_rows_ignored_not_erroring(self):
        df = read(EMPTY_ROWS_CSV)
        result = analysis.validate_csv(df)
        self.assertTrue(result.is_valid, result.error_messages())
        self.assertEqual(len(result.cleaned_df), 2)
        self.assertTrue(any("empty row" in w for w in result.warnings))

    def test_missing_required_column_reported(self):
        df = read(MISSING_REQUIRED_COL_CSV)
        result = analysis.validate_csv(df)
        self.assertFalse(result.is_valid)
        messages = result.error_messages()
        self.assertTrue(any("Branch" in m for m in messages), messages)

    def test_no_subject_columns_reported(self):
        df = read(NO_SUBJECT_COLUMNS_CSV)
        result = analysis.validate_csv(df)
        self.assertFalse(result.is_valid)
        messages = result.error_messages()
        self.assertTrue(any("No subject-mark columns" in m for m in messages), messages)

class TestPerformanceCalculation(unittest.TestCase):
    def test_overall_percentage_and_category(self):
        marks = {"Data Structures": 78, "DBMS": 82, "Python": 88, "Mathematics": 71, "Java": 85}
        result = analysis.calculate_student_performance(marks)
        self.assertAlmostEqual(result["overall_percentage"], 80.8, places=1)
        self.assertEqual(result["performance_category"], "Excellent")

    def test_categories_consistent_boundaries(self):
        self.assertEqual(analysis.categorize(80), "Excellent")
        self.assertEqual(analysis.categorize(79.99), "Good")
        self.assertEqual(analysis.categorize(60), "Good")
        self.assertEqual(analysis.categorize(59.99), "Average")
        self.assertEqual(analysis.categorize(40), "Average")
        self.assertEqual(analysis.categorize(39.99), "At Risk")
        self.assertEqual(analysis.categorize(0), "At Risk")
        self.assertEqual(analysis.categorize(100), "Excellent")

class TestRiskAssessment(unittest.TestCase):
    def test_high_risk_flagged(self):
        marks = {"Python": 30, "Java": 35, "DBMS": 50}
        overall = analysis.calculate_overall_percentage(list(marks.values()))
        risk = analysis.assess_risk(marks, overall)
        self.assertEqual(risk["risk_level"], "High Risk")

    def test_low_risk_flagged(self):
        marks = {"Python": 90, "Java": 85, "DBMS": 88}
        overall = analysis.calculate_overall_percentage(list(marks.values()))
        risk = analysis.assess_risk(marks, overall)
        self.assertEqual(risk["risk_level"], "Low Risk")

    def test_moderate_risk_flagged(self):
        marks = {"Python": 65, "Java": 30, "DBMS": 70}
        overall = analysis.calculate_overall_percentage(list(marks.values()))
        risk = analysis.assess_risk(marks, overall)
        self.assertIn(risk["risk_level"], ("Moderate Risk", "High Risk"))

    def test_never_claims_trained_model_accuracy(self):
        marks = {"Python": 65, "Java": 60}
        overall = analysis.calculate_overall_percentage(list(marks.values()))
        risk = analysis.assess_risk(marks, overall)
        for value in risk.values():
            self.assertNotIn("accuracy", str(value).lower())

class TestSubjectStatistics(unittest.TestCase):
    def test_subject_statistics_shape(self):
        df = read(VALID_CSV)
        result = analysis.validate_csv(df)
        self.assertTrue(result.is_valid)
        stats = analysis.subject_statistics(result.cleaned_df, result.subject_columns)
        self.assertEqual(len(stats), 5)
        ds_stats = next(s for s in stats if s["subject"] == "Data Structures")
        self.assertEqual(ds_stats["average"], round((86 + 74 + 62) / 3, 2))
        self.assertEqual(ds_stats["highest"], 86)
        self.assertEqual(ds_stats["lowest"], 62)

if __name__ == "__main__":
    unittest.main()
