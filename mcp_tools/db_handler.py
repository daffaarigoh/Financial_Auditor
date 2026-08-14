import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from config.settings import DB_PATH


@contextmanager
def get_connection():
    """Context manager for SQLite connection — auto-closes and auto-commits on success."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Creates the audit_records table if it doesn't already exist."""
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            vendor_name TEXT,
            invoice_number TEXT,
            invoice_date TEXT,
            subtotal REAL,
            tax_amount REAL,
            total_amount REAL,
            status TEXT NOT NULL,
            has_stamp BOOLEAN,
            has_signature BOOLEAN,
            math_check_passed BOOLEAN,
            anomalies_json TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)


def insert_audit_record(record_data: dict) -> int:
    """Inserts a new audit record and returns the new row ID."""
    anomalies_str = json.dumps(record_data.get("anomalies", []))

    with get_connection() as conn:
        cursor = conn.execute("""
        INSERT INTO audit_records (
            file_name, file_path, vendor_name, invoice_number, invoice_date,
            subtotal, tax_amount, total_amount, status, has_stamp, has_signature,
            math_check_passed, anomalies_json, summary, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record_data.get("file_name", "Unknown"),
            record_data.get("file_path", ""),
            record_data.get("vendor_name", "-"),
            record_data.get("invoice_number", "-"),
            record_data.get("invoice_date", "-"),
            record_data.get("subtotal", 0.0),
            record_data.get("tax_amount", 0.0),
            record_data.get("total_amount", 0.0),
            record_data.get("status", "ANOMALY_DETECTED"),
            record_data.get("has_stamp", False),
            record_data.get("has_signature", False),
            record_data.get("math_check_passed", False),
            anomalies_str,
            record_data.get("summary", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        return cursor.lastrowid


def get_all_records() -> list[dict]:
    """Fetches all audit records ordered by most recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_records ORDER BY created_at DESC"
        ).fetchall()

    results = []
    for row in rows:
        item = dict(row)
        # Parse JSON anomalies and drop the raw JSON column
        item["anomalies"] = json.loads(item.pop("anomalies_json") or "[]")
        results.append(item)

    return results


def get_record_count() -> dict:
    """Returns total, valid, and anomaly counts without fetching all rows."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM audit_records").fetchone()[0]
        valid = conn.execute(
            "SELECT COUNT(*) FROM audit_records WHERE status = 'VALID'"
        ).fetchone()[0]

    return {"total": total, "valid": valid, "anomaly": total - valid}


def clear_all_records() -> bool:
    """Deletes all records from the audit_records table."""
    with get_connection() as conn:
        conn.execute("DELETE FROM audit_records")
    return True


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
