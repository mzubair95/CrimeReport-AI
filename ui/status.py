"""View report status (section 27) — simple lookup by tracking ID."""
from __future__ import annotations

import streamlit as st

from database.database import get_report_audited
from ui.components import brand_header, go_to, card

STATUS_COLORS = {
    "RECEIVED": "crai-badge-ok", "SUBMITTED": "crai-badge-ok",
    "IN_REVIEW": "crai-badge-ai", "CLOSED": "",
}


def render():
    brand_header(show_tagline=False)
    st.markdown("## 🔎 View Report Status")

    auto_lookup_id = st.session_state.pop("status_lookup_id", "")
    report_id = st.text_input(
        "Enter your Report ID", value=auto_lookup_id, placeholder="e.g. CR-2026-000143",
    )

    if st.button("Look up", type="primary", use_container_width=True) or auto_lookup_id:
        report_id_clean = (report_id or "").strip().upper()
        if not report_id_clean:
            st.error("Please enter a report ID.")
        else:
            # Sensitive categories (Domestic Violence, Harassment) get an
            # audit_log entry on every lookup (FIR spec §4.4); other
            # categories pass through untouched.
            report = get_report_audited(report_id_clean, actor="user")
            if not report:
                st.error("No report found with that ID. Double-check and try again.")
            else:
                badge = STATUS_COLORS.get(report["status"], "")
                card(f"""
                    <b>Report ID:</b> {report['report_id']}<br>
                    <b>Status:</b> <span class="crai-badge {badge}">{report['status']}</span><br>
                    <b>Type:</b> {report.get('category') or report.get('crime_type') or 'Unclassified'}<br>
                    <b>Submitted:</b> {report['created_at'][:19].replace('T', ' ')} UTC<br>
                    <b>Routed to:</b> {report.get('authority_name') or 'Demo backend'}
                """)
                with st.expander("Summary"):
                    st.write(report.get("summary") or "No summary available.")

    st.write("")
    if st.button("⬅️ Back to Home", use_container_width=True):
        go_to("home")
