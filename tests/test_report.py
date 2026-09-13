"""
Tests for report generation and the database layer — these run entirely
offline (no Gemini/Pinecone required).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reports.generator import to_json, to_pdf
from database.database import (
    init_db, get_report, submit_report, dashboard_stats, list_reports,
    update_status, get_review_actions,
)

SAMPLE_REPORT = {
    "description": "My car window was broken and my phone was stolen.",
    "summary": "The user reports their vehicle window was broken and a phone was taken.",
    "category": "Theft / Pickpocketing",
    "crime_type": "Theft / Pickpocketing",
    "confidence": 0.8,
    "severity": "Medium",
    "severity_reason": "Property crime already concluded, no ongoing danger.",
    "incident_date": "2026-09-12",
    "incident_time": "21:00",
    "location": "Shopping center parking lot",
    "language": "English",
    "anonymous": False,
    "facts": {"object_involved": "mobile phone"},
    "qa_history": [{"question": "Was anyone injured?", "answer": "No"}],
    "evidence": [{"name": "car.jpg", "type": "image", "ai_analysis": "Broken window visible",
                  "privacy_flags": []}],
    "reporter": {"full_name": "Jane Doe", "phone": "555-0100", "email": "jane@example.com"},
    "verification_flags": [{"flag_type": "low_detail", "message": "Very little detail provided.",
                             "severity": "info"}],
    "duplicate_matches": [],
}


def test_json_export_roundtrip():
    payload = to_json(SAMPLE_REPORT, "CR-2026-000001")
    data = json.loads(payload)
    assert data["report_id"] == "CR-2026-000001"
    assert data["category"] == "Theft / Pickpocketing"


def test_pdf_generation_produces_bytes():
    pdf_bytes = to_pdf(SAMPLE_REPORT, "CR-2026-000001")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"


def test_anonymous_report_omits_reporter_details():
    anon = dict(SAMPLE_REPORT)
    anon["anonymous"] = True
    pdf_bytes = to_pdf(anon, "CR-2026-000002")
    assert isinstance(pdf_bytes, bytes)


def test_database_create_and_fetch(tmp_path, monkeypatch):
    import config.settings as settings
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.sqlite3")
    import database.database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    init_db()

    result = submit_report(dict(SAMPLE_REPORT))
    assert result["report_id"].startswith("CR-")
    assert result["status"] == "Submitted"

    fetched = get_report(result["report_id"])
    assert fetched is not None
    assert fetched["category"] == "Theft / Pickpocketing"
    assert fetched["severity"] == "Medium"
    assert fetched["verification_flags"][0]["flag_type"] == "low_detail"
    assert fetched["reporter"]["full_name"] == "Jane Doe"

    # Status workflow + review-action audit trail (FR-10)
    update_status(result["report_id"], "Under Review", reviewer_id="test-reviewer", note="Looks fine")
    updated = get_report(result["report_id"])
    assert updated["status"] == "Under Review"
    actions = get_review_actions(result["report_id"])
    assert len(actions) == 1
    assert actions[0]["reviewer_id"] == "test-reviewer"

    filtered = list_reports(category="Theft / Pickpocketing")
    assert any(r["report_id"] == result["report_id"] for r in filtered)

    stats = dashboard_stats()
    assert stats["total"] >= 1
    assert "Medium" in stats["by_severity"] or stats["by_severity"]


def test_anonymous_report_stores_no_reporter_details(tmp_path, monkeypatch):
    import config.settings as settings
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test2.sqlite3")
    import database.database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test2.sqlite3")
    init_db()

    anon = dict(SAMPLE_REPORT)
    anon["anonymous"] = True
    result = submit_report(anon)
    fetched = get_report(result["report_id"])
    assert fetched["reporter"] == {}


if __name__ == "__main__":
    test_json_export_roundtrip()
    test_pdf_generation_produces_bytes()
    print("Basic report tests passed.")
