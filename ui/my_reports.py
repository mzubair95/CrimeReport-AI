"""
My Reports (PRD §14 home action) — since this MVP has no user accounts,
"my reports" means reports submitted from this browser session (tracked in
st.session_state), plus a manual case-ID lookup for anyone checking a report
from a different session/device.
"""
from __future__ import annotations

import streamlit as st

from database.database import get_report
from ui.components import brand_header, go_to, card

STATUS_COLORS = {
    "Submitted": "crai-badge-ai", "Under Review": "crai-badge-ai",
    "Assigned": "crai-badge-ai", "Resolved": "crai-badge-ok", "Closed": "",
}


def render():
    brand_header(show_tagline=False)
    st.markdown("## 📄 My Reports")

    my_ids = st.session_state.get("my_report_ids", [])
    if my_ids:
        st.caption("Reports you've submitted this session:")
        for rid in my_ids:
            report = get_report(rid)
            if report:
                _render_card(report)
    else:
        st.caption("You haven't submitted any reports this session yet.")

    st.divider()
    st.markdown("### Look up a report by Case ID")
    auto_lookup_id = st.session_state.pop("status_lookup_id", "")
    report_id = st.text_input(
        "Case ID", value=auto_lookup_id, placeholder="e.g. CR-2026-000143",
        label_visibility="collapsed",
    )
    if st.button("Look up", type="primary", use_container_width=True) or auto_lookup_id:
        report_id_clean = (report_id or "").strip().upper()
        if not report_id_clean:
            st.error("Please enter a case ID.")
        else:
            report = get_report(report_id_clean)
            if not report:
                st.error("No report found with that ID. Double-check and try again.")
            else:
                _render_card(report, expanded=True)

    st.write("")
    if st.button("⬅️ Back to Home", use_container_width=True):
        go_to("home")


def _render_card(report: dict, expanded: bool = False):
    badge = STATUS_COLORS.get(report["status"], "")
    card(f"""
        <b>Case ID:</b> {report['report_id']}<br>
        <b>Status:</b> <span class="crai-badge {badge}">{report['status']}</span><br>
        <b>Category:</b> {report.get('category') or 'Unclassified'}<br>
        <b>Priority:</b> {report.get('severity') or 'Not assessed'}<br>
        <b>Submitted:</b> {report['created_at'][:19].replace('T', ' ')} UTC
    """)
    with st.expander("Summary", expanded=expanded):
        st.write(report.get("summary") or "No summary available.")
