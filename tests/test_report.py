"""
Tests for report generation and the database layer — these run entirely
offline (no Gemini/Pinecone required).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reports.generator import to_json, to_pdf
from database.database import init_db, create_report, get_report, submit_report, dashboard_stats

SAMPLE_REPORT = {
    "description": "My car window was broken and my phone was stolen.",
    "summary": "The user reports their vehicle window was broken and a phone was taken.",
    "crime_type": "Theft",
    "confidence": 0.8,
    "incident_date": "2026-09-12",
    "incident_time": "21:00",
    "location": "Shopping center parking lot",
    "facts": {"object_involved": "mobile phone"},
    "qa_history": [{"question": "Was anyone injured?", "answer": "No"}],
    "evidence": [{"name": "car.jpg", "type": "image", "ai_analysis": "Broken window visible"}],
    "victim": {"full_name": "Jane Doe", "phone": "555-0100", "email": "jane@example.com"},
}


def test_json_export_roundtrip():
    payload = to_json(SAMPLE_REPORT, "CR-2026-000001")
    data = json.loads(payload)
    assert data["report_id"] == "CR-2026-000001"
    assert data["crime_type"] == "Theft"


def test_pdf_generation_produces_bytes():
    pdf_bytes = to_pdf(SAMPLE_REPORT, "CR-2026-000001")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"


def test_database_create_and_fetch(tmp_path, monkeypatch):
    import config.settings as settings
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.sqlite3")
    import database.database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    init_db()
    result = submit_report(dict(SAMPLE_REPORT))
    assert result["report_id"].startswith("CR-")
    fetched = get_report(result["report_id"])
    assert fetched is not None
    assert fetched["crime_type"] == "Theft"
    stats = dashboard_stats()
    assert stats["total"] >= 1


if __name__ == "__main__":
    test_json_export_roundtrip()
    test_pdf_generation_produces_bytes()
    print("Basic report tests passed.")
