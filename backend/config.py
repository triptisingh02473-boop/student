import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "student_performance_db"),
}

DB_BACKEND = os.environ.get("DB_BACKEND", "auto").lower()

SQLITE_FALLBACK_PATH = os.path.join(BASE_DIR, "student_performance_fallback.db")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"csv"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
