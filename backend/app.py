import io
import os
import sys

import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, Response

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import database as db
from analysis import validate_csv, subject_statistics, assess_risk

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
    static_folder=os.path.join(FRONTEND_DIR, "static"),
)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
app.secret_key = config.SECRET_KEY

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS

def db_error_response(e: db.DatabaseError, status=500):
    return jsonify({
        "success": False,
        "error": "A database error occurred. Please check that MySQL is running and configured "
                  "correctly (see README.md).",
        "details": str(e),
    }), status

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/upload")
def upload_page():
    return render_template("upload.html")

@app.route("/subjects")
def subjects_page():
    return render_template("subjects.html")

@app.route("/prediction")
def prediction_page():
    return render_template("prediction.html")

@app.route("/reports")
def reports_page():
    return render_template("reports.html")

@app.route("/student/<student_id>")
def student_detail_page(student_id):
    return render_template("student_detail.html", student_id=student_id)

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "csv_file" not in request.files:
        return jsonify({"success": False, "error": "No file was included in the request."}), 400

    file = request.files["csv_file"]

    if file.filename == "":
        return jsonify({"success": False, "error": "No file was selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": f"Unsupported file type for '{file.filename}'. Please upload a .csv file."
        }), 400

    try:
        raw_bytes = file.read()
        if len(raw_bytes) == 0:
            return jsonify({"success": False, "error": "The uploaded file is empty."}), 400
        df = pd.read_csv(io.BytesIO(raw_bytes))
    except pd.errors.EmptyDataError:
        return jsonify({"success": False, "error": "The uploaded CSV file has no data."}), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"The file could not be read as a CSV. Details: {e}"
        }), 400

    result = validate_csv(df)
    if not result.is_valid:
        return jsonify({
            "success": False,
            "error": "CSV upload failed. Please fix the following issue(s) and try again:",
            "validation_errors": result.error_messages(),
            "warnings": result.warnings,
        }), 400

    save_path = os.path.join(config.UPLOAD_FOLDER, file.filename)
    try:
        with open(save_path, "wb") as f:
            f.write(raw_bytes)
    except OSError:
        pass

    try:
        import_result = db.import_dataset(result.cleaned_df, result.subject_columns, file.filename)
    except db.DatabaseError as e:
        return db_error_response(e)

    return jsonify({
        "success": True,
        "message": (
            f"Successfully imported {import_result['num_students']} students "
            f"and {import_result['num_subjects']} subjects."
        ),
        "num_students": import_result["num_students"],
        "num_subjects": import_result["num_subjects"],
        "subjects": result.subject_columns,
        "warnings": result.warnings,
    })

@app.route("/api/sample-csv")
def api_sample_csv():
    sample = (
        "Student_ID,Student_Name,Branch,Semester,Data Structures,DBMS,Python,Mathematics,Java\n"
        "STU001,Aarav Mehta,CSE,3,86,82,91,78,88\n"
        "STU002,Diya Sharma,CSE,3,74,79,81,72,76\n"
        "STU003,Kabir Rao,CSE,3,62,68,65,59,64\n"
    )
    return Response(
        sample,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample_student_data_template.csv"},
    )

@app.route("/api/dashboard")
def api_dashboard():
    try:
        stats = db.get_dashboard_stats()
        stats["subject_overview"] = db.get_subject_overview() if stats["has_data"] else []
        last_upload = db.get_last_upload_info()
        if last_upload and "uploaded_at" in last_upload and last_upload["uploaded_at"]:
            last_upload["uploaded_at"] = str(last_upload["uploaded_at"])
        stats["last_upload"] = last_upload
        return jsonify({"success": True, **stats})
    except db.DatabaseError as e:
        return db_error_response(e)

@app.route("/api/subjects")
def api_subjects():
    try:
        subjects = db.list_subjects()
        details = [db.get_subject_detail(s) for s in subjects]
        return jsonify({"success": True, "subjects": details})
    except db.DatabaseError as e:
        return db_error_response(e)

@app.route("/api/subjects/<subject_name>")
def api_subject_detail(subject_name):
    try:
        detail = db.get_subject_detail(subject_name)
        if detail is None:
            return jsonify({"success": False, "error": f"Subject '{subject_name}' not found."}), 404
        return jsonify({"success": True, "subject": detail})
    except db.DatabaseError as e:
        return db_error_response(e)

@app.route("/api/students")
def api_students():
    try:
        return jsonify({"success": True, "students": db.list_students()})
    except db.DatabaseError as e:
        return db_error_response(e)

@app.route("/api/students/<student_id>")
def api_student_detail(student_id):
    try:
        detail = db.get_student_detail(student_id)
        if detail is None:
            return jsonify({"success": False, "error": f"Student '{student_id}' not found."}), 404
        return jsonify({"success": True, "student": detail})
    except db.DatabaseError as e:
        return db_error_response(e)

@app.route("/api/prediction/<student_id>")
def api_prediction(student_id):
    try:
        detail = db.get_student_detail(student_id)
        if detail is None:
            return jsonify({"success": False, "error": f"Student '{student_id}' not found."}), 404

        marks_by_subject = {m["subject_name"]: float(m["marks"]) for m in detail["marks"]}
        risk = assess_risk(marks_by_subject, detail["overall_percentage"])

        return jsonify({
            "success": True,
            "student_id": detail["student_id"],
            "student_name": detail["student_name"],
            "overall_percentage": detail["overall_percentage"],
            "performance_category": detail["performance_category"],
            "prediction": risk,
            "note": (
                "This is a transparent, rule-based performance risk assessment derived from "
                "the student's current subject marks. It is not a trained machine-learning "
                "model, since the uploaded data has no historical outcome label to train on."
            ),
        })
    except db.DatabaseError as e:
        return db_error_response(e)

@app.route("/api/prediction")
def api_prediction_all():
    try:
        students = db.list_students()
        results = []
        for s in students:
            detail = db.get_student_detail(s["student_id"])
            marks_by_subject = {m["subject_name"]: float(m["marks"]) for m in detail["marks"]}
            risk = assess_risk(marks_by_subject, detail["overall_percentage"])
            results.append({
                "student_id": detail["student_id"],
                "student_name": detail["student_name"],
                "overall_percentage": detail["overall_percentage"],
                "performance_category": detail["performance_category"],
                "risk_level": risk["risk_level"],
                "reasoning": risk["reasoning"],
            })
        return jsonify({"success": True, "predictions": results})
    except db.DatabaseError as e:
        return db_error_response(e)

@app.route("/api/reports")
def api_reports():
    try:
        stats = db.get_dashboard_stats()
        if not stats["has_data"]:
            return jsonify({"success": True, "has_data": False})

        return jsonify({
            "success": True,
            "has_data": True,
            "category_distribution": stats["category_distribution"],
            "subject_overview": db.get_subject_overview(),
            "top_students": db.get_top_students(5),
            "students_needing_attention": db.get_students_needing_attention(5),
            "class_average": stats["class_average"],
            "total_students": stats["total_students"],
        })
    except db.DatabaseError as e:
        return db_error_response(e)

@app.route("/api/health")
def api_health():
    try:
        db.has_active_dataset()
        return jsonify({
            "success": True,
            "database": "connected",
            "backend": db.active_backend(),
        })
    except db.DatabaseError as e:
        return jsonify({
            "success": False,
            "database": "unreachable",
            "backend": db.active_backend(),
            "details": str(e),
        }), 500

if __name__ == "__main__":
    print(f"[startup] Database backend in use: {db.active_backend()}")
    app.run(debug=True, host="0.0.0.0", port=5000)
