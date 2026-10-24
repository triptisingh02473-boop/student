# Student Academic Performance Analysis and Prediction System

A college mini-project: a teacher uploads a class CSV, the Flask backend
reads it with pandas, validates it, dynamically detects subject columns,
stores everything in MySQL, and the dashboard / subject analysis /
prediction / reports pages update live from that data.

No student data is hardcoded anywhere in the application — every page is
driven by whatever CSV was most recently uploaded.

**Runs immediately, MySQL or not.** MySQL is the primary, documented
database (see section 3). If `mysql-connector-python` isn't installed, or
MySQL isn't reachable, the app automatically falls back to a local SQLite
file so it still runs end to end — see section 3a. The app always prints
which backend is actually active, both at startup and at `/api/health`.

---

## 1. Project structure

```
student_perf/
├── backend/
│   ├── app.py           Flask routes + JSON APIs
│   ├── database.py      All MySQL access (import, queries)
│   ├── analysis.py       CSV validation, subject detection, performance calc, prediction
│   └── config.py        MySQL connection settings (env-var overridable)
├── frontend/
│   ├── templates/       Jinja2 HTML pages
│   └── static/
│       ├── css/style.css
│       └── js/          One JS file per page, calling the JSON APIs
├── sql/
│   └── schema.sql       MySQL schema (students, subjects, marks, performance, uploads)
├── sample_data/         Sample CSVs (valid, invalid, different subjects, derived columns)
├── uploads/             Uploaded CSVs are copied here for audit purposes
├── tests/               Automated tests (see section 7)
├── requirements.txt
└── README.md
```

---

## 2. Install Python dependencies

Requires Python 3.10+.

```bash
cd student_perf
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Configure and create the MySQL database

1. Make sure a MySQL server (5.7+ / 8.x) is installed and running.
2. Create the database and tables using the provided schema:

   ```bash
   mysql -u root -p < sql/schema.sql
   ```

   This creates a database called `student_performance_db` with five tables:
   `students`, `subjects`, `student_marks`, `student_performance`, `uploads`.

3. Set your MySQL credentials as environment variables (defaults shown):

   ```bash
   export DB_HOST=localhost
   export DB_PORT=3306
   export DB_USER=root
   export DB_PASSWORD=yourpassword
   export DB_NAME=student_performance_db
   ```

   (On Windows PowerShell use `$env:DB_PASSWORD="yourpassword"`, etc.)

   If you skip this step, the app defaults to `host=localhost, user=root,
   password="", database=student_performance_db`.

---

## 3a. Database backend: MySQL vs. the automatic fallback

Set with the `DB_BACKEND` environment variable:

| Value | Behavior |
|---|---|
| `auto` (default) | Try MySQL first. If `mysql-connector-python` isn't installed, or the MySQL server can't be reached, automatically use a local SQLite file instead (`student_performance_fallback.db`, created next to this README). A warning is printed either way — it's never silent. |
| `mysql` | Require MySQL. Raise a clear error instead of falling back if it's missing/unreachable. Use this once you've done the MySQL setup in section 3 and want to be sure it's actually being used. |
| `sqlite` | Force the local fallback database, skipping MySQL entirely. Useful for a quick demo run with zero setup. |

```bash
export DB_BACKEND=mysql   # e.g., to confirm your MySQL setup is really being used
```

The fallback uses the exact same schema and SQL as `sql/schema.sql` (translated
automatically for SQLite's syntax), so behavior is identical either way — this
is a convenience for running the app without database setup, not a different
implementation. **For the actual college submission, run with MySQL configured
and set `DB_BACKEND=mysql`** so there's no ambiguity about which database was used.

---

## 4. Start the Flask server

```bash
cd backend
python3 app.py
```

The app runs at **http://localhost:5000**.

You can verify the database connection at any time by visiting
`http://localhost:5000/api/health`.

---

## 5. Upload a CSV

1. Open `http://localhost:5000/upload`.
2. Click "Download Sample CSV Template" if you want a ready-made file, or
   use one of the files in `sample_data/`.
3. Click the drop zone, choose your `.csv` file, and click **Upload CSV**.
4. On success you'll see: *"Successfully imported N students and M
   subjects."* The Dashboard, Subject Analysis, Prediction, and Reports
   pages all immediately reflect the new data — a fresh upload replaces
   the previously active dataset.
5. If the CSV has a problem, you'll see exactly which row/column is at
   fault (e.g. *"Row 5, DBMS: Mark must be a number between 0 and
   100."*) and nothing is written to the database.

---

## 6. Expected CSV format

```
Student_ID,Student_Name,Branch,Semester,<Subject 1>,<Subject 2>,...
STU001,Aarav Mehta,CSE,3,86,82,91,78,88
STU002,Diya Sharma,CSE,3,74,79,81,72,76
```

- `Student_ID`, `Student_Name`, `Branch`, `Semester` are required metadata
  columns and can appear in any order.
- Every other column is treated as a subject **if** its values are
  numeric marks between 0 and 100. You can have any number of subjects,
  with any names — they are detected automatically, not hardcoded.
- If your CSV already has `Overall_Percentage` or `Performance_Category`
  columns (e.g. re-exported from this system), they are ignored on
  import and recalculated from the raw subject marks.
- Completely blank rows are silently ignored. Duplicate `Student_ID`
  values, out-of-range marks, and missing required fields all cause the
  entire upload to be rejected with a precise error message — nothing
  is partially imported.

Sample files for testing are in `sample_data/`:
- `sample_students.csv` — valid, 10 students, 5 subjects
- `sample_students_different_subjects.csv` — valid, different subject
  names, proves dynamic detection isn't hardcoded to 5 known subjects
- `sample_with_derived_columns.csv` — valid, includes
  `Overall_Percentage`/`Performance_Category` which must be ignored
- `invalid_sample.csv` — deliberately broken (out-of-range mark, blank
  name, duplicate Student_ID) to test rejection

---

## 7. How the performance calculation works

For every student:

```
Overall percentage = average of all subject marks
```

Performance category (used consistently on every page):

| Overall % | Category  |
|-----------|-----------|
| 80 – 100  | Excellent |
| 60 – 79   | Good      |
| 40 – 59   | Average   |
| Below 40  | At Risk   |

**Prediction / risk assessment** (Prediction page): this is a
transparent, rule-based assessment — not a trained machine-learning
model — because the uploaded CSV has no historical "did this student
succeed" label to train against. It combines the overall percentage,
the number of subjects below 40, and the spread between the strongest
and weakest subject into a `Low Risk` / `Moderate Risk` / `High Risk`
label with a plain-language reason. The UI labels it explicitly as a
risk assessment and never claims a fabricated accuracy score.

---

## 8. Testing

This project includes four layers of automated tests:

```bash
# 1. Pure CSV validation / subject-detection / calculation logic (no DB needed)
python3 -m unittest tests.test_analysis -v

# 2. The automatic MySQL -> SQLite fallback logic itself (database.get_connection())
python3 tests/test_db_backend_fallback.py

# 3. Full import pipeline against database.py's real code
#    (CSV -> validate -> import_dataset -> every query function)
python3 tests/test_full_pipeline_sqlite.py

# 4. Full HTTP pipeline against the real Flask app (real multipart upload
#    through request.files, every page and API route)
python3 tests/test_flask_http_e2e.py
```

All four suites run with zero setup — no MySQL server, no environment
variables — because they exercise the app's built-in SQLite fallback
(test 2 tests that fallback directly; tests 3 and 4 swap in an equivalent
adapter to double-check `database.py`'s SQL against a second, independent
harness). This is genuinely how the app behaves out of the box, not a
mock of it — you can confirm this yourself by just running `python3
backend/app.py` with no MySQL installed and watching it print
`Database backend in use: sqlite (...)` and work normally.

**This was also verified with real, live HTTP requests during
development** — starting the actual Flask dev server and uploading
`sample_data/sample_students.csv` and `sample_data/invalid_sample.csv`
with `curl -F "csv_file=@...`, not just through the test client.

**For the actual college submission, run with MySQL configured** (steps
in sections 3–3a) and set `DB_BACKEND=mysql` so grading is unambiguous
about which database was used. The schema in `sql/schema.sql` uses
standard SQL (INNER JOIN, GROUP BY, foreign keys) with no exotic
MySQL-only features, so behavior is identical to what you've already
seen working on the fallback.

---

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/api/health` returns `database: unreachable` | MySQL isn't running, or `DB_USER`/`DB_PASSWORD`/`DB_NAME` are wrong |
| "Access denied for user" | Wrong `DB_PASSWORD`, or the MySQL user lacks privileges on `student_performance_db` |
| Upload says "No subject-mark columns were found" | Your CSV's only extra columns are non-numeric (e.g. text remarks) — add at least one numeric 0–100 mark column |
| Dashboard shows "Ready for class data" forever after uploading | Check the browser console / Flask terminal for an error from `/api/upload` — the import likely failed validation or a DB error occurred |
