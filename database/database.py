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
                category TEXT,
                is_emergency INTEGER,
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
        # Legal reference lookups shown to the user for a report (FIR spec §3.1) —
        # persisted separately so the exact citation shown at the time is
        # auditable even if the knowledge base changes later.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS legal_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT NOT NULL REFERENCES reports(report_id),
                statute TEXT NOT NULL,
                section_number TEXT NOT NULL,
                section_title TEXT,
                cognizable TEXT,
                bailable TEXT,
                punishment_range TEXT,
                source_citation TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                disclaimer_shown INTEGER NOT NULL DEFAULT 1
            )
        """)
        # Confirmations required before submission (FIR spec §3.1/Step 6) —
        # e.g. the false-reporting notice acknowledgment and the accuracy
        # consent, each with its own durable timestamp.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT NOT NULL REFERENCES reports(report_id),
                confirmation_type TEXT NOT NULL,
                confirmed_at TEXT NOT NULL
            )
        """)
        # Lightweight migration for demo DBs created before these columns existed.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(reports)")}
        if "category" not in existing_cols:
            conn.execute("ALTER TABLE reports ADD COLUMN category TEXT")
        if "is_emergency" not in existing_cols:
            conn.execute("ALTER TABLE reports ADD COLUMN is_emergency INTEGER")


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
                report_id, created_at, status, category, is_emergency, crime_type,
                confidence, incident_date, incident_time, location, description,
                summary, authority_id, authority_name, facts_json, qa_history_json,
                evidence_json, victim_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            report_id, now, "RECEIVED",
            report.get("category"), 1 if report.get("is_emergency") else 0,
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


def save_legal_references(report_id: str, refs: list[dict]) -> None:
    """Persists the exact legal citations shown to the user for this report
    (FIR spec §3.1) — a durable, auditable record separate from whatever the
    knowledge base looks like later."""
    if not refs:
        return
    with _lock, _connect() as conn:
        for ref in refs:
            conn.execute("""
                INSERT INTO legal_references (
                    report_id, statute, section_number, section_title,
                    cognizable, bailable, punishment_range, source_citation,
                    retrieved_at, disclaimer_shown
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                report_id, ref.get("statute", ""), ref.get("section_number", ""),
                ref.get("section_title"), ref.get("cognizable"), ref.get("bailable"),
                ref.get("punishment_range"), ref.get("source_citation", ""),
                ref.get("retrieved_at", datetime.now(timezone.utc).isoformat()),
                1 if ref.get("disclaimer_shown", True) else 0,
            ))


def get_legal_references(report_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM legal_references WHERE report_id = ? ORDER BY id", (report_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def save_confirmation(report_id: str, confirmation_type: str) -> str:
    """Records a required confirmation (FIR spec Step 6/§3.1) with a durable
    timestamp — e.g. "false_reporting_notice" or "accuracy_consent". Returns
    the timestamp recorded."""
    confirmed_at = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO confirmations (report_id, confirmation_type, confirmed_at) "
            "VALUES (?,?,?)",
            (report_id, confirmation_type, confirmed_at),
        )
    return confirmed_at


def get_confirmations(report_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM confirmations WHERE report_id = ? ORDER BY id", (report_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_report(report_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    if not row:
        return None
    result = _row_to_dict(row)
    result["legal_references"] = get_legal_references(report_id)
    result["confirmations"] = get_confirmations(report_id)
    return result


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
            "SELECT COALESCE(category, crime_type) AS cat, COUNT(*) c FROM reports "
            "GROUP BY cat ORDER BY c DESC"
        ).fetchall()
        by_date = conn.execute(
            "SELECT substr(created_at,1,10) d, COUNT(*) c FROM reports GROUP BY d ORDER BY d"
        ).fetchall()
    return {
        "total": total,
        "open": open_count,
        "submitted": submitted,
        "by_type": {r["cat"] or "Unknown": r["c"] for r in by_type},
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

    category = report.get("category") or report.get("crime_type", "Other")
    authority = next((a for a in AUTHORITIES if category in a["handles"]), AUTHORITIES[0])
    report["authority_id"] = authority["id"]
    report["authority_name"] = authority["name"]

    report_id = create_report(report)
    save_legal_references(report_id, report.get("legal_references") or [])
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
