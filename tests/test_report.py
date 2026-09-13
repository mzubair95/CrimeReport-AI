"""
Tests for report generation and the database layer — these run entirely
offline (no Gemini/Pinecone required).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reports.generator import to_json, to_pdf
from reports.fir_template import to_fir_pdf
from database.database import (
    init_db, create_report, get_report, submit_report, dashboard_stats, decrypt_cnic,
)

SAMPLE_REPORT = {
    "description": "My car window was broken and my phone was stolen.",
    "summary": "The user reports their vehicle window was broken and a phone was taken.",
    "category": "Robbery/Theft",  # Step 1 user-selected, canonical
    "crime_type": "Robbery/Theft",  # AI-suggested signal, same here
    "confidence": 0.8,
    "incident_date": "2026-09-12",
    "incident_time": "21:00",
    "location": "Shopping center parking lot",
    "is_emergency": False,
    "facts": {"object_involved": "mobile phone"},
    "qa_history": [{"question": "Was anyone injured?", "answer": "No"}],
    "evidence": [{"name": "car.jpg", "type": "image", "ai_analysis": "Broken window visible"}],
    "victim": {"full_name": "Jane Doe", "cnic": "12345-1234567-1",
               "phone": "555-0100", "email": "jane@example.com"},
    "legal_references": [{"statute": "PPC", "section_number": "379",
                           "section_title": "Punishment for theft", "cognizable": "unknown",
                           "bailable": "bailable", "punishment_range": "up to 3 years",
                           "source_citation": "https://example.com/ppc"}],
    "confirmations": [{"confirmation_type": "accuracy_consent", "confirmed_at": "2026-09-12T21:00:00Z"}],
}


def test_json_export_roundtrip():
    payload = to_json(SAMPLE_REPORT, "CR-2026-000001")
    data = json.loads(payload)
    assert data["report_id"] == "CR-2026-000001"
    assert data["category"] == "Robbery/Theft"


def test_pdf_generation_produces_bytes():
    pdf_bytes = to_pdf(SAMPLE_REPORT, "CR-2026-000001")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"


def test_fir_pdf_generation_produces_bytes():
    pdf_bytes = to_fir_pdf(SAMPLE_REPORT, "CR-2026-000001")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"


def test_database_create_and_fetch(tmp_path, monkeypatch):
    import config.settings as settings
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setattr(settings, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(settings, "FIELD_ENCRYPTION_KEY",
                         "c2D33nKYX82jYJBRNkCGjVy4b6kt4BJ9FdoTM76J2i4=")
    import database.database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setattr(db, "REPORTS_DIR", tmp_path)
    init_db()
    result = submit_report(dict(SAMPLE_REPORT))
    assert result["report_id"].startswith("CR-")
    fetched = get_report(result["report_id"])
    assert fetched is not None
    assert fetched["category"] == "Robbery/Theft"
    assert result["authority_name"] == "Demo Local Police Department (non-emergency)"
    assert fetched["is_emergency"] == 0

    # CNIC must never appear in plaintext on the general accessor...
    assert "cnic" not in fetched["victim"]
    assert "reporter_cnic_enc" not in fetched
    # ...but must decrypt correctly via the audited path.
    cnic = decrypt_cnic(result["report_id"], actor="test")
    assert cnic == "12345-1234567-1"

    stats = dashboard_stats()
    assert stats["total"] >= 1


if __name__ == "__main__":
    test_json_export_roundtrip()
    test_pdf_generation_produces_bytes()
    test_fir_pdf_generation_produces_bytes()
    print("Basic report tests passed.")
