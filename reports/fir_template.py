"""
Step 8 — FIR draft generation (docs/FIR_TECHNICAL_SPEC.md §2/§5).

Produces a formatted "First Information Report" DRAFT document referencing
the exact legal sections shown to the user in Step 4/6. This is explicitly
NOT a submission to any real police e-FIR system — every copy is labeled a
draft the user brings to the station themselves (Step 9's honesty
requirement), matching the same "no real agency is contacted" principle as
database.database.submit_report().
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

from config.settings import DISCLAIMER
from reports.generator import _styles, _field_table

FIR_TEMPLATE_VERSION = "1.0"


def to_fir_pdf(report: dict, report_id: str) -> bytes:
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                             topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    story = []

    story.append(Paragraph("FIRST INFORMATION REPORT — DRAFT", styles["ReportTitle"]))
    story.append(Paragraph(
        f"Report ID: {report_id} &nbsp;|&nbsp; Prepared: "
        f"{datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')}",
        styles["ReportSubtitle"]))

    # Unmissable, boxed clarification (spec Step 9: set expectations correctly)
    notice_table = Table([[Paragraph(
        "<b>This is a DRAFT, not an official filing.</b> Crime Report.AI has NOT "
        "submitted this to any police e-FIR system. Bring this document "
        f"(printed or on your phone) to <b>{report.get('authority_name', 'your nearest police station')}</b> "
        "to file an official report, or contact them directly.",
        styles["Body"])]], colWidths=[6.6 * inch])
    notice_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#F59E0B")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(notice_table)
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Complainant Information", styles["SectionHeading"]))
    victim = report.get("victim") or {}
    story.append(_field_table([
        ("Full name", victim.get("full_name")),
        ("CNIC", victim.get("cnic")),
        ("Phone", victim.get("phone")),
        ("Email", victim.get("email")),
        ("Address", victim.get("address")),
    ]))

    story.append(Paragraph("Incident Details", styles["SectionHeading"]))
    story.append(_field_table([
        ("Category", report.get("category") or report.get("crime_type")),
        ("Date", report.get("incident_date")),
        ("Time", report.get("incident_time")),
        ("Location", report.get("location")),
        ("Reported as emergency", "Yes" if report.get("is_emergency") else "No"),
    ]))

    story.append(Paragraph("Narrative (AI-Assisted Summary)", styles["SectionHeading"]))
    story.append(Paragraph(report.get("summary") or report.get("description") or "N/A",
                            styles["Body"]))

    qa_history = report.get("qa_history") or []
    if qa_history:
        story.append(Paragraph("Additional Details", styles["SectionHeading"]))
        story.append(_field_table([(qa.get("question", ""), qa.get("answer", "")) for qa in qa_history]))

    legal_refs = report.get("legal_references") or []
    story.append(Paragraph("Applicable Legal Sections", styles["SectionHeading"]))
    if legal_refs:
        for ref in legal_refs:
            story.append(Paragraph(
                f"<b>{ref.get('statute', '')} § {ref.get('section_number', '')}</b> — "
                f"{ref.get('section_title', '')}. Cognizable: {ref.get('cognizable', 'unknown')}. "
                f"Bailable: {ref.get('bailable', 'unknown')}. "
                f"Punishment: {ref.get('punishment_range', 'unknown')}.",
                styles["Small"]))
        story.append(Paragraph(
            "These references are informational drafts and have not been verified by a "
            "lawyer — confirm the applicable section(s) with the investigating officer.",
            styles["Small"]))
    else:
        story.append(Paragraph(
            "No legal references were looked up for this report. Consult the "
            "investigating officer or a lawyer for the applicable section(s).",
            styles["Body"]))

    evidence = report.get("evidence") or []
    story.append(Paragraph("Evidence", styles["SectionHeading"]))
    if evidence:
        story.append(_field_table([
            (f"File {i + 1}", f"{e.get('name', 'unnamed')} ({e.get('type', 'file')})")
            for i, e in enumerate(evidence)
        ]))
    else:
        story.append(Paragraph("No evidence files attached.", styles["Body"]))

    confirmations = report.get("confirmations") or []
    if confirmations:
        story.append(Paragraph("Confirmations", styles["SectionHeading"]))
        story.append(_field_table([
            (c.get("confirmation_type", ""), c.get("confirmed_at", "")) for c in confirmations
        ]))

    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#E2E8F0")))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(DISCLAIMER, styles["Small"]))

    doc.build(story)
    return buf.getvalue()
