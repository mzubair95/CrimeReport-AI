"""
Step 6 — False reporting notice & confirmation (docs/FIR_TECHNICAL_SPEC.md §2).

Shown immediately before submission, for every category, regardless of what
was reviewed in Step 5. The user must explicitly acknowledge this notice —
separately from the general accuracy consent already collected in the
evidence/reporter-info step — before the report can be submitted.
"""
from __future__ import annotations

import logging

import streamlit as st

from ai.legal_service import get_false_reporting_notice
from database.database import submit_report, save_confirmation, save_fir_document
from reports.generator import to_json, to_pdf
from reports.fir_template import to_fir_pdf, FIR_TEMPLATE_VERSION
from ui.components import brand_header, go_to, progress_bar, card
from ui.state import draft

logger = logging.getLogger("crime_report_ai.ui.false_reporting_notice")


def render():
    brand_header(show_tagline=False)
    progress_bar(7, 8, "Step 7 of 8 — Before you submit")

    d = draft()
    if not d.get("category"):
        go_to("category_select")
        return

    st.markdown("## ⚠️ Important Notice")
    st.write("Filing a false report is a criminal offense. Please make sure everything "
             "you've provided is accurate before continuing.")

    try:
        notice = get_false_reporting_notice()
    except Exception:
        logger.exception("Failed to load false-reporting notice")
        notice = {}

    if notice:
        card(f"""
            <b>{notice.get('statute', 'PPC')} — Section {notice.get('section_number', '182')}</b><br>
            <i>{notice.get('section_title', '')}</i><br><br>
            {notice.get('summary', '')}<br><br>
            <b>Punishment range:</b> {notice.get('punishment_range', 'unknown')}
        """)
        st.caption(f"Source: {notice.get('source_citation', 'N/A')} — informational only, "
                   "not verified by a lawyer.")

    st.write("")
    confirmed = st.checkbox(
        "I confirm that the information I have provided is accurate to the best of my "
        "knowledge, and I understand that knowingly filing a false report may be a "
        "criminal offense under the law referenced above.",
        key="false_reporting_ack",
    )

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Back", use_container_width=True):
            go_to("review")
    with col2:
        if st.button("✅ SUBMIT REPORT", type="primary", use_container_width=True,
                      disabled=not confirmed):
            _submit(d)


def _submit(d: dict):
    with st.spinner("Generating your report and submitting..."):
        try:
            result = submit_report(dict(d))
            report_id = result["report_id"]
            confirmed_at_1 = save_confirmation(report_id, "false_reporting_notice")
            confirmed_at_2 = save_confirmation(report_id, "accuracy_consent")

            # The FIR draft (Step 8) includes the confirmations just recorded —
            # build that list in-memory rather than re-reading the DB.
            fir_data = dict(d)
            fir_data["confirmations"] = [
                {"confirmation_type": "false_reporting_notice", "confirmed_at": confirmed_at_1},
                {"confirmation_type": "accuracy_consent", "confirmed_at": confirmed_at_2},
            ]

            pdf_bytes = to_pdf(d, report_id)
            json_str = to_json(d, report_id)
            fir_pdf_bytes = to_fir_pdf(fir_data, report_id)
            save_fir_document(report_id, fir_pdf_bytes, FIR_TEMPLATE_VERSION)
        except Exception:
            logger.exception("Report generation/submission failed")
            st.error("We're temporarily unable to generate your report. "
                      "Please try again in a moment.")
            return

    st.session_state.last_report_id = report_id
    st.session_state.last_submission = result
    st.session_state.last_pdf_bytes = pdf_bytes
    st.session_state.last_json_str = json_str
    st.session_state.last_fir_pdf_bytes = fir_pdf_bytes
    go_to("submitted")
