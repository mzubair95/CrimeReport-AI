"""
Demo persistence layer (section 23/24) using SQLite — the "Demo backend"
reports are submitted to. Swappable: replace this module's functions with
calls to a real database/API without touching the UI layer (section 36).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from config.settings import DB_PATH

_lock = threading.Lock()


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                crime_type TEXT,
                confidence REAL,
                incident_date TEXT,
                incident_time TEXT,
                location TEXT,
                description TEXT,
                summary TEXT,
                authority_id TEXT,
                authority_name TEXT,
                facts_json TEXT,
                qa_history_json TEXT,
                evidence_json TEXT,
                victim_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS report_seq (
                year TEXT PRIMARY KEY,
                counter INTEGER NOT NULL
            )
        """)


def _next_report_id() -> str:
    year = str(datetime.now(timezone.utc).year)
    with _lock, _connect() as conn:
        row = conn.execute("SELECT counter FROM report_seq WHERE year = ?", (year,)).fetchone()
        counter = (row["counter"] if row else 0) + 1
        conn.execute(
            "INSERT INTO report_seq(year, counter) VALUES (?, ?) "
            "ON CONFLICT(year) DO UPDATE SET counter = ?",
            (year, counter, counter),
        )
    return f"CR-{year}-{counter:06d}"


def create_report(report: dict) -> str:
    """Persists a report and returns its newly generated tracking ID."""
    report_id = _next_report_id()
    now = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as conn:
        conn.execute("""
            INSERT INTO reports (
                report_id, created_at, status, crime_type, confidence,
                incident_date, incident_time, location, description, summary,
                authority_id, authority_name, facts_json, qa_history_json,
                evidence_json, victim_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            report_id, now, "RECEIVED",
            report.get("crime_type"), report.get("confidence"),
            report.get("incident_date"), report.get("incident_time"),
            report.get("location"), report.get("description"), report.get("summary"),
            report.get("authority_id"), report.get("authority_name"),
            json.dumps(report.get("facts", {})),
            json.dumps(report.get("qa_history", [])),
            json.dumps(report.get("evidence", [])),
            json.dumps(report.get("victim", {})),
        ))
    return report_id


def get_report(report_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_reports(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM reports ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_status(report_id: str, status: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE reports SET status = ? WHERE report_id = ?", (status, report_id))


def dashboard_stats() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM reports").fetchone()["c"]
        open_count = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE status != 'CLOSED'"
        ).fetchone()["c"]
        submitted = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE status IN ('RECEIVED','SUBMITTED','IN_REVIEW')"
        ).fetchone()["c"]
        by_type = conn.execute(
            "SELECT crime_type, COUNT(*) c FROM reports GROUP BY crime_type ORDER BY c DESC"
        ).fetchall()
        by_date = conn.execute(
            "SELECT substr(created_at,1,10) d, COUNT(*) c FROM reports GROUP BY d ORDER BY d"
        ).fetchall()
    return {
        "total": total,
        "open": open_count,
        "submitted": submitted,
        "by_type": {r["crime_type"] or "Unknown": r["c"] for r in by_type},
        "by_date": {r["d"]: r["c"] for r in by_date},
    }


def submit_report(report: dict) -> dict:
    """
    Modular submission layer (section 23). For this hackathon MVP, every
    report goes to the demo backend (this SQLite database) and is routed to
    whichever configured "authority" handles its crime type. No real agency
    is contacted — this function is the single seam where a real, authorized
    government API integration would be plugged in later, without changing
    any UI code.
    """
    from config.settings import AUTHORITIES

    crime_type = report.get("crime_type", "Other")
    authority = next((a for a in AUTHORITIES if crime_type in a["handles"]), AUTHORITIES[0])
    report["authority_id"] = authority["id"]
    report["authority_name"] = authority["name"]

    report_id = create_report(report)
    return {
        "report_id": report_id,
        "status": "RECEIVED",
        "authority_name": authority["name"],
        "note": "Submitted to the demo backend. No real law-enforcement agency "
                "has been contacted by this hackathon prototype.",
    }


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("facts_json", "qa_history_json", "evidence_json", "victim_json"):
        try:
            d[key.replace("_json", "")] = json.loads(d.pop(key) or "{}")
        except (json.JSONDecodeError, TypeError):
            d[key.replace("_json", "")] = {}
    return d
