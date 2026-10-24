from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
METADATA_COLUMNS = ["Student_ID", "Student_Name", "Branch", "Semester"]
DERIVED_COLUMNS = {"Overall_Percentage", "Performance_Category"}
REQUIRED_METADATA_COLUMNS = ["Student_ID", "Student_Name", "Branch", "Semester"]
MARK_MIN = 0
MARK_MAX = 100
PERFORMANCE_BANDS = [
    (80, 100.0000001, "Excellent"),
    (60, 80, "Good"),
    (40, 60, "Average"),
    (-0.0000001, 40, "At Risk"),
]
@dataclass
class ValidationError:
    row: int | None
    column: str | None
    message: str
def as_dict(self) -> dict:
        return {"row": self.row, "column": self.column, "message": self.message}
def display(self) -> str:
        if self.row is not None and self.column is not None:
            return f"Row {self.row}, {self.column}: {self.message}"
        if self.row is not None:
            return f"Row {self.row}: {self.message}"
        return self.message
@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    subject_columns: list[str] = field(default_factory=list)
    cleaned_df: "pd.DataFrame | None" = None
    warnings: list[str] = field(default_factory=list)

    def error_messages(self) -> list[str]:
        return [e.display() for e in self.errors]

def detect_subject_columns(df: pd.DataFrame) -> list[str]:

    subject_cols = []
    for col in df.columns:
        stripped = str(col).strip()
        if stripped in METADATA_COLUMNS:
            continue
        if stripped in DERIVED_COLUMNS:
            continue
        subject_cols.append(col)
    return subject_cols

def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False

def validate_csv(df: pd.DataFrame) -> ValidationResult:

    errors: list[ValidationError] = []
    warnings: list[str] = []

    if df is None or df.shape[1] == 0:
        return ValidationResult(is_valid=False, errors=[
            ValidationError(None, None, "The uploaded file has no columns and could not be read as a CSV.")
        ])

    def validate_csv(df: pd.DataFrame) -> ValidationResult:
        errors: list[ValidationError] = []
    warnings: list[str] = []

    if df is None or df.shape[1] == 0:
        return ValidationResult(is_valid=False, errors=[
            ValidationError(None, None, "The uploaded file has no columns and could not be read as a CSV.")
        ])

    df = df.rename(columns=lambda c: str(c).strip())
    column_aliases = {
        "Student_ID": ["Student_ID", "Student ID", "ID", "Roll No", "Roll Number"],
        "Student_Name": ["Student_Name", "Student Name", "Name"],
        "Branch": ["Branch", "Department", "Program"],
        "Semester": ["Semester", "Sem"]
    }
    rename_map = {}

    for standard_name, aliases in column_aliases.items():
        for column in df.columns:
            if str(column).strip().lower() in [alias.lower() for alias in aliases]:
                rename_map[column] = standard_name
                break
            df = df.rename(columns=rename_map)

    def row_is_completely_empty(row) -> bool:
        return all(_is_blank(v) for v in row)

    empty_row_mask = df.apply(row_is_completely_empty, axis=1)
    n_empty = int(empty_row_mask.sum())
    if n_empty:
        warnings.append(f"{n_empty} completely empty row(s) were found and ignored.")
    df = df[~empty_row_mask].reset_index(drop=True)

    if df.shape[0] == 0:
        errors.append(ValidationError(None, None, "The CSV file does not contain any student data rows."))
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    missing_meta = [c for c in REQUIRED_METADATA_COLUMNS if c not in df.columns]
    if missing_meta:
        errors.append(ValidationError(
            None, None,
            "The CSV is missing required column(s): " + ", ".join(missing_meta) +
            ". Expected columns: Student_ID, Student_Name, Branch, Semester, followed by subject marks."
        ))

        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    candidate_subject_cols = detect_subject_columns(df)

    if DERIVED_COLUMNS & set(df.columns):
        found = sorted(DERIVED_COLUMNS & set(df.columns))
        warnings.append(
            f"Column(s) {', '.join(found)} were found in the file but will be ignored and "
            "recalculated automatically from the subject marks."
        )

    if not candidate_subject_cols:
        errors.append(ValidationError(
            None, None,
            "No subject-mark columns were found. The CSV must contain at least one subject "
            "column with numeric marks between 0 and 100, in addition to Student_ID, "
            "Student_Name, Branch, and Semester."
        ))
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    valid_subject_cols: list[str] = []
    rejected_subject_cols: dict[str, str] = {}

    for col in candidate_subject_cols:
        series = df[col]
        non_blank = series[~series.apply(_is_blank)]
        if non_blank.empty:
            rejected_subject_cols[col] = "This column contains no values and cannot be used as a subject."
            continue
        numeric_convertible = pd.to_numeric(non_blank, errors="coerce")
        if numeric_convertible.isna().all():
            rejected_subject_cols[col] = (
                "This column does not contain numeric marks, so it was not treated as a subject."
            )
            continue
        valid_subject_cols.append(col)

    for col, reason in rejected_subject_cols.items():
        warnings.append(f"Column '{col}' was ignored: {reason}")

    if not valid_subject_cols:
        errors.append(ValidationError(
            None, None,
            "None of the remaining columns contain valid numeric subject marks (0-100)."
        ))
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    seen_ids: dict[str, int] = {}
    duplicate_ids: dict[str, list[int]] = {}

    for idx, row in df.iterrows():
        excel_row = idx + 2

        student_id = row.get("Student_ID")
        student_name = row.get("Student_Name")
        branch = row.get("Branch")
        semester = row.get("Semester")

        if _is_blank(student_id):
            errors.append(ValidationError(excel_row, "Student_ID", "Student ID cannot be empty."))
        else:
            sid = str(student_id).strip()
            if sid in seen_ids:
                duplicate_ids.setdefault(sid, [seen_ids[sid]]).append(excel_row)
            else:
                seen_ids[sid] = excel_row

        if _is_blank(student_name):
            errors.append(ValidationError(excel_row, "Student_Name", "Student name cannot be empty."))

        if _is_blank(branch):
            errors.append(ValidationError(excel_row, "Branch", "Branch cannot be empty."))

        if _is_blank(semester):
            errors.append(ValidationError(excel_row, "Semester", "Semester cannot be empty."))
        else:
            try:
                sem_val = int(float(semester))
                if sem_val < 1 or sem_val > 12:
                    errors.append(ValidationError(
                        excel_row, "Semester", f"Semester value '{semester}' is not valid (expected 1-12)."
                    ))
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    excel_row, "Semester", f"Semester must be a whole number, got '{semester}'."
                ))

        for col in valid_subject_cols:
            value = row.get(col)
            if _is_blank(value):
                errors.append(ValidationError(excel_row, col, "Mark is missing."))
                continue
            try:
                mark = float(value)
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    excel_row, col, f"Mark must be a number between {MARK_MIN} and {MARK_MAX}, got '{value}'."
                ))
                continue
            if mark < MARK_MIN or mark > MARK_MAX:
                errors.append(ValidationError(
                    excel_row, col, f"Mark must be a number between {MARK_MIN} and {MARK_MAX}, got {value}."
                ))

    for sid, rows in duplicate_ids.items():
        errors.append(ValidationError(
            None, "Student_ID",
            f"Student ID '{sid}' appears more than once (rows {', '.join(str(r) for r in rows)})."
        ))

    if errors:
        return ValidationResult(
            is_valid=False, errors=errors, subject_columns=valid_subject_cols, warnings=warnings
        )

    cleaned = df[REQUIRED_METADATA_COLUMNS + valid_subject_cols].copy()
    cleaned["Student_ID"] = cleaned["Student_ID"].astype(str).str.strip()
    cleaned["Student_Name"] = cleaned["Student_Name"].astype(str).str.strip()
    cleaned["Branch"] = cleaned["Branch"].astype(str).str.strip()
    cleaned["Semester"] = cleaned["Semester"].apply(lambda v: int(float(v)))
    for col in valid_subject_cols:
        cleaned[col] = cleaned[col].astype(float)

    return ValidationResult(
        is_valid=True,
        errors=[],
        subject_columns=valid_subject_cols,
        cleaned_df=cleaned,
        warnings=warnings,
    )

def categorize(overall_percentage: float) -> str:
    for low, high, label in PERFORMANCE_BANDS:
        if low <= overall_percentage < high:
            return label

    if overall_percentage >= 80:
        return "Excellent"
    return "At Risk"

def calculate_overall_percentage(marks: list[float]) -> float:
    if not marks:
        return 0.0
    return round(sum(marks) / len(marks), 2)

def calculate_student_performance(marks_by_subject: dict[str, float]) -> dict:
    marks = list(marks_by_subject.values())
    overall = calculate_overall_percentage(marks)
    category = categorize(overall)
    return {
        "overall_percentage": overall,
        "performance_category": category,
    }

def assess_risk(marks_by_subject: dict[str, float], overall_percentage: float) -> dict:

    if not marks_by_subject:
        return {
            "risk_level": "Unknown",
            "reasoning": "No subject marks are available for this student.",
            "weak_subjects": [],
            "consistency": None,
        }

    marks = list(marks_by_subject.values())
    weak_subjects = [s for s, m in marks_by_subject.items() if m < 40]
    borderline_subjects = [s for s, m in marks_by_subject.items() if 40 <= m < 50]
    spread = max(marks) - min(marks)

    if overall_percentage < 40 or len(weak_subjects) >= 2:
        risk_level = "High Risk"
        reasoning = (
            f"Overall average is {overall_percentage}% and the student is failing "
            f"({len(weak_subjects)}) subject(s) below 40 marks."
            if weak_subjects else
            f"Overall average is {overall_percentage}%, which is below the passing threshold."
        )
    elif overall_percentage < 60 or weak_subjects or spread >= 40:
        risk_level = "Moderate Risk"
        reasons = []
        if overall_percentage < 60:
            reasons.append(f"overall average is {overall_percentage}%")
        if weak_subjects:
            reasons.append(f"weak in {', '.join(weak_subjects)} (below 40)")
        if spread >= 40:
            reasons.append(f"large gap of {spread:.0f} marks between strongest and weakest subject")
        reasoning = "Flagged because " + "; ".join(reasons) + "."
    else:
        risk_level = "Low Risk"
        reasoning = f"Overall average is {overall_percentage}% with no failing subjects."

    return {
        "risk_level": risk_level,
        "reasoning": reasoning,
        "weak_subjects": weak_subjects,
        "borderline_subjects": borderline_subjects,
        "consistency": round(spread, 2),
    }

def subject_statistics(cleaned_df: pd.DataFrame, subject_columns: list[str]) -> list[dict]:
    stats = []
    for col in subject_columns:
        series = cleaned_df[col]
        weak = cleaned_df[series < 40][["Student_ID", "Student_Name"]].to_dict("records")
        strong = cleaned_df[series >= 80][["Student_ID", "Student_Name"]].to_dict("records")
        stats.append({
            "subject": col,
            "average": round(float(series.mean()), 2),
            "highest": round(float(series.max()), 2),
            "lowest": round(float(series.min()), 2),
            "num_students": int(series.shape[0]),
            "weak_students": weak,
            "strong_students": strong,
        })
    return stats

