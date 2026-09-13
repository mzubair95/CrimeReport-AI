"""
Demo persistence layer using SQLite — the "Authorized Reviewer" backend
reports land in. Swappable: replace this module's functions with calls to a
real database/API without touching the UI layer.

Schema follows the PRD's Data Model (§15):
  Incident        -> reports table
  AI Assessment   -> columns on reports (severity, confidence, verification
                     flags, model_version) — versioned per report; a demo
                     scale doesn't need a separate assessment-history table
  Related Incident -> related_incidents table (duplicate/correlation)
  Review Action   -> review_actions table (reviewer audit trail)
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
                category TEXT,
                crime_type TEXT,
                confidence REAL,
                severity TEXT,
                severity_reason TEXT,
                incident_date TEXT,
                incident_time TEXT,
                location TEXT,
                description TEXT,
                summary TEXT,
                language TEXT,
                anonymous INTEGER NOT NULL DEFAULT 0,
                model_version TEXT,
                facts_json TEXT,
                qa_history_json TEXT,
                evidence_json TEXT,
                reporter_json TEXT,
                verification_flags_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS report_seq (
                year TEXT PRIMARY KEY,
                counter INTEGER NOT NULL
            )
        """)
        # Related Incident (PRD §15) — duplicate/correlation results from
        # ai/duplicate_detector.py, persisted so a reviewer can see why two
        # cases were linked.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS related_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT NOT NULL REFERENCES reports(report_id),
                related_report_id TEXT NOT NULL REFERENCES reports(report_id),
                similarity_score REAL NOT NULL,
                reason TEXT,
                detected_at TEXT NOT NULL
            )
        """)
        # Review Action (PRD §15) — audit trail of reviewer decisions (FR-10).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_actions (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT NOT NULL REFERENCES reports(report_id),
                reviewer_id TEXT NOT NULL,
                action TEXT NOT NULL,
                note TEXT,
                occurred_at TEXT NOT NULL
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
    """Persists a report (status starts at 'Submitted') and returns its
    newly generated tracking ID."""
    report_id = _next_report_id()
    now = datetime.now(timezone.utc).isoformat()
    reporter = {} if report.get("anonymous") else dict(report.get("reporter") or {})
    with _lock, _connect() as conn:
        conn.execute("""
            INSERT INTO reports (
                report_id, created_at, status, category, crime_type, confidence,
                severity, severity_reason, incident_date, incident_time, location,
                description, summary, language, anonymous, model_version,
                facts_json, qa_history_json, evidence_json, reporter_json,
                verification_flags_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            report_id, now, "Submitted",
            report.get("category"), report.get("crime_type"), report.get("confidence"),
            report.get("severity"), report.get("severity_reason"),
            report.get("incident_date"), report.get("incident_time"),
            report.get("location"), report.get("description"), report.get("summary"),
            report.get("language"), 1 if report.get("anonymous") else 0,
            report.get("model_version"),
            json.dumps(report.get("facts", {})),
            json.dumps(report.get("qa_history", [])),
            json.dumps(report.get("evidence", [])),
            json.dumps(reporter),
            json.dumps(report.get("verification_flags", [])),
        ))
    return report_id


def save_related_incidents(report_id: str, matches: list[dict]) -> None:
    """Persists duplicate/related-incident matches found at submission time
    (PRD §15 Related Incident, AI Modules "Duplicate Detection")."""
    if not matches:
        return
    now = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as conn:
        for m in matches:
            conn.execute("""
                INSERT INTO related_incidents (report_id, related_report_id, similarity_score, reason, detected_at)
                VALUES (?,?,?,?,?)
            """, (report_id, m["report_id"], m["similarity"], m.get("reason", ""), now))


def get_related_incidents(report_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM related_incidents WHERE report_id = ? ORDER BY similarity_score DESC",
            (report_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def record_review_action(report_id: str, reviewer_id: str, action: str, note: str = "") -> None:
    """Audit trail for reviewer decisions (FR-10) — e.g. status changes."""
    with _lock, _connect() as conn:
        conn.execute("""
            INSERT INTO review_actions (report_id, reviewer_id, action, note, occurred_at)
            VALUES (?,?,?,?,?)
        """, (report_id, reviewer_id, action, note, datetime.now(timezone.utc).isoformat()))


def get_review_actions(report_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM review_actions WHERE report_id = ? ORDER BY action_id", (report_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_status(report_id: str, status: str, reviewer_id: str = "reviewer", note: str = "") -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE reports SET status = ? WHERE report_id = ?", (status, report_id))
    record_review_action(report_id, reviewer_id, f"status_changed:{status}", note)


def get_report(report_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    if not row:
        return None
    result = _row_to_dict(row)
    result["related_incidents"] = get_related_incidents(report_id)
    result["review_actions"] = get_review_actions(report_id)
    return result


def list_reports(limit: int = 200, category: str | None = None, severity: str | None = None,
                  status: str | None = None) -> list[dict]:
    query = "SELECT * FROM reports WHERE 1=1"
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def dashboard_stats() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM reports").fetchone()["c"]
        open_count = conn.execute(
            "SELECT COUNT(*) c FROM reports WHERE status NOT IN ('Resolved','Closed')"
        ).fetchone()["c"]
        by_status = conn.execute(
            "SELECT status, COUNT(*) c FROM reports GROUP BY status"
        ).fetchall()
        by_category = conn.execute(
            "SELECT category, COUNT(*) c FROM reports GROUP BY category ORDER BY c DESC"
        ).fetchall()
        by_severity = conn.execute(
            "SELECT severity, COUNT(*) c FROM reports GROUP BY severity"
        ).fetchall()
        by_date = conn.execute(
            "SELECT substr(created_at,1,10) d, COUNT(*) c FROM reports GROUP BY d ORDER BY d"
        ).fetchall()
    return {
        "total": total,
        "open": open_count,
        "by_status": {r["status"]: r["c"] for r in by_status},
        "by_category": {r["category"] or "Unknown": r["c"] for r in by_category},
        "by_severity": {r["severity"] or "Unassessed": r["c"] for r in by_severity},
        "by_date": {r["d"]: r["c"] for r in by_date},
    }


def submit_report(report: dict) -> dict:
    """
    Section 23-style modular submission layer. For this hackathon MVP, every
    report goes to the demo backend (this SQLite database) with status
    'Submitted', ready for an authorized reviewer to triage.
    """
    report_id = create_report(report)
    matches = report.get("duplicate_matches") or []
    save_related_incidents(report_id, matches)
    return {
        "report_id": report_id,
        "status": "Submitted",
        "note": "Submitted to the demo review queue. An authorized reviewer "
                "will triage this report; no real emergency dispatch has "
                "been contacted by this hackathon prototype.",
    }


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("facts_json", "qa_history_json", "evidence_json", "reporter_json",
                "verification_flags_json"):
        target = key.replace("_json", "")
        default = "[]" if target in ("qa_history", "evidence", "verification_flags") else "{}"
        try:
            d[target] = json.loads(d.pop(key) or default)
        except (json.JSONDecodeError, TypeError):
            d[target] = [] if target in ("qa_history", "evidence", "verification_flags") else {}
    return d
