"""
Report generation (section 22): structured JSON export + a formatted PDF,
built with reportlab so no external template engine is required.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

from config.settings import DISCLAIMER


def to_json(report: dict, report_id: str) -> str:
    """Structured JSON export of the full report (section 22)."""
    payload = {
        "report_id": report_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **report,
    }
    return json.dumps(payload, indent=2, default=str)


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", fontSize=20, leading=24,
                               textColor=colors.HexColor("#0B1330"), spaceAfter=4))
    styles.add(ParagraphStyle(name="ReportSubtitle", fontSize=10,
                               textColor=colors.HexColor("#64748B"), spaceAfter=16))
    styles.add(ParagraphStyle(name="SectionHeading", fontSize=13, leading=16,
                               textColor=colors.HexColor("#123B91"), spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle(name="Body", fontSize=10.5, leading=15))
    styles.add(ParagraphStyle(name="Small", fontSize=8, leading=11,
                               textColor=colors.HexColor("#64748B")))
    return styles


def _field_table(rows: list[tuple[str, str]]) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", getSampleStyleSheet()["Normal"]), v or "Not provided"]
            for k, v in rows]
    t = Table(data, colWidths=[1.6 * inch, 4.4 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    return t


def to_pdf(report: dict, report_id: str) -> bytes:
    """Render the confirmed report to a PDF and return the raw bytes."""
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                             topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    story = []

    story.append(Paragraph("Crime Report.AI — Incident Report", styles["ReportTitle"]))
    story.append(Paragraph(
        f"Report ID: {report_id} &nbsp;|&nbsp; Generated: "
        f"{datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')}",
        styles["ReportSubtitle"]))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#E2E8F0")))

    story.append(Paragraph("Incident", styles["SectionHeading"]))
    story.append(_field_table([
        ("Type", report.get("category") or report.get("crime_type")),
        ("Date", report.get("incident_date")),
        ("Time", report.get("incident_time")),
        ("Location", report.get("location")),
    ]))

    story.append(Paragraph("Summary", styles["SectionHeading"]))
    story.append(Paragraph(report.get("summary") or report.get("description") or "N/A",
                            styles["Body"]))

    story.append(Paragraph("Original Description (User Provided)", styles["SectionHeading"]))
    story.append(Paragraph(report.get("description") or "N/A", styles["Body"]))

    qa_history = report.get("qa_history") or []
    if qa_history:
        story.append(Paragraph("Follow-up Questions & Answers", styles["SectionHeading"]))
        story.append(_field_table([(qa.get("question", ""), qa.get("answer", "")) for qa in qa_history]))

    evidence = report.get("evidence") or []
    story.append(Paragraph("Evidence", styles["SectionHeading"]))
    if evidence:
        story.append(_field_table([
            (f"File {i + 1}", f"{e.get('name', 'unnamed')} ({e.get('type', 'file')})")
            for i, e in enumerate(evidence)
        ]))
        for e in evidence:
            analysis = e.get("ai_analysis")
            if analysis:
                story.append(Paragraph(
                    f"<i>AI-analyzed (not confirmed fact) — {e.get('name')}:</i> {analysis}",
                    styles["Small"]))
    else:
        story.append(Paragraph("No evidence files attached.", styles["Body"]))

    legal_refs = report.get("legal_references") or []
    if legal_refs:
        story.append(Paragraph("Applicable Legal References (Unverified — See Disclaimer)",
                                styles["SectionHeading"]))
        for ref in legal_refs:
            story.append(Paragraph(
                f"<b>{ref.get('statute', '')} § {ref.get('section_number', '')}</b> — "
                f"{ref.get('section_title', '')}. Cognizable: {ref.get('cognizable', 'unknown')}. "
                f"Bailable: {ref.get('bailable', 'unknown')}. "
                f"Punishment: {ref.get('punishment_range', 'unknown')}.",
                styles["Small"]))

    victim = report.get("victim") or {}
    if victim:
        story.append(Paragraph("Reporter Information", styles["SectionHeading"]))
        story.append(_field_table([
            ("Full name", victim.get("full_name")),
            ("Phone", victim.get("phone")),
            ("Email", victim.get("email")),
            ("Address", victim.get("address")),
            ("Preferred contact", victim.get("preferred_contact")),
        ]))

    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#E2E8F0")))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(DISCLAIMER, styles["Small"]))

    doc.build(story)
    return buf.getvalue()
