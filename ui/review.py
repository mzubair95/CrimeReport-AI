"""Report review screen — editable AI-generated summary, verification
flags, and duplicate-check results, with explicit user confirmation
required before submission."""
from __future__ import annotations

import logging

import streamlit as st

from ai.summarizer import build_incident_summary
from ai.verification import run_all_checks
from ai.duplicate_detector import find_duplicates, index_report
from database.database import submit_report
from reports.generator import to_json, to_pdf
from ui.components import brand_header, go_to, progress_bar, card
from ui.state import draft

logger = logging.getLogger("crime_report_ai.ui.review")

SEVERITY_BADGE = {
    "Critical": "crai-badge", "High": "crai-badge",
    "Medium": "crai-badge-ai", "Low": "crai-badge-ok",
}


def render():
    brand_header(show_tagline=False)
    progress_bar(5, 5, "Step 5 of 5 — Review your report")

    d = draft()

    if not d.get("summary"):
        with st.spinner("Preparing your report summary..."):
            try:
                d["summary"] = build_incident_summary(d)
            except Exception:
                logger.exception("Summary generation failed")
                d["summary"] = d.get("description", "")

    if not d.get("verification_flags"):
        with st.spinner("Running verification checks..."):
            d["verification_flags"] = run_all_checks(d.get("description", ""), d.get("qa_history", []))

    if not d.get("duplicate_matches"):
        try:
            d["duplicate_matches"] = find_duplicates(d.get("category", ""), d.get("description", ""))
        except Exception:
            logger.exception("Duplicate detection failed")

    st.markdown("## Review Your Report")

    badge_class = SEVERITY_BADGE.get(d.get("severity"), "")
    card(f"""
        <b>Incident</b><br>
        Type: {d.get('category') or d.get('crime_type') or 'Not classified'}<br>
        Priority: <span class="crai-badge {badge_class}">{d.get('severity') or 'Not assessed'}</span>
        <span style="font-size:0.85rem; color:#64748B;"> — {d.get('severity_reason', '')}</span><br>
        Date: {d.get('incident_date') or 'Not provided'}<br>
        Time: {d.get('incident_time') or 'Not provided'}<br>
        Location: {d.get('location') or 'Not provided'}
    """)

    card(f"""
        <b>AI Summary</b> <span class="crai-badge crai-ai">AI-generated — please verify</span><br><br>
        {d.get('summary', '')}
    """)

    with st.expander("Original description (user provided)"):
        st.write(d.get("description") or "N/A")

    if d.get("qa_history"):
        with st.expander(f"Follow-up answers ({len(d['qa_history'])})"):
            for qa in d["qa_history"]:
                st.markdown(f"**{qa['question']}** — {qa['answer']}")

    evidence = d.get("evidence", [])
    card(f"<b>Evidence</b><br>{len(evidence)} file(s) attached" if evidence
         else "<b>Evidence</b><br>No files attached")

    flags = d.get("verification_flags", [])
    if flags:
        with st.expander(f"🔎 Verification notes ({len(flags)})", expanded=True):
            st.caption("These are neutral flags for the reviewer — not an accusation, "
                       "and not a determination that anything here is false.")
            for f in flags:
                st.markdown(f"- **{f['flag_type'].replace('_', ' ').title()}**: {f['message']}")

    dupes = d.get("duplicate_matches", [])
    if dupes:
        with st.expander(f"🔁 Possibly related reports ({len(dupes)})"):
            for m in dupes:
                st.markdown(f"- `{m['report_id']}` — {m['reason']}")

    reporter = d.get("reporter", {})
    if d.get("anonymous"):
        card("<b>Personal Information</b><br>Reporting anonymously — no contact details collected.")
    else:
        card(f"""
            <b>Personal Information</b><br>
            {reporter.get('full_name', 'N/A')}<br>
            {reporter.get('phone', '')} {('· ' + reporter.get('email')) if reporter.get('email') else ''}
        """)

    st.caption(
        "By confirming, you acknowledge this report may contain AI-generated "
        "content that you have reviewed for accuracy. This does not replace "
        "emergency services or legal advice."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✏️ Edit", use_container_width=True):
            go_to("evidence")
    with col2:
        if st.button("✅ CONFIRM & SUBMIT", type="primary", use_container_width=True):
            _confirm_and_submit(d)


def _confirm_and_submit(d: dict):
    with st.spinner("Generating your report and submitting..."):
        try:
            result = submit_report(dict(d))
            report_id = result["report_id"]
            index_report(report_id, d.get("category", ""), d.get("description", ""))
            pdf_bytes = to_pdf(d, report_id)
            json_str = to_json(d, report_id)
        except Exception:
            logger.exception("Report generation/submission failed")
            st.error("We're temporarily unable to generate your report. "
                      "Please try again in a moment.")
            return

    st.session_state.last_report_id = report_id
    st.session_state.last_submission = result
    st.session_state.last_pdf_bytes = pdf_bytes
    st.session_state.last_json_str = json_str
    my_reports = st.session_state.setdefault("my_report_ids", [])
    my_reports.insert(0, report_id)
    go_to("submitted")
