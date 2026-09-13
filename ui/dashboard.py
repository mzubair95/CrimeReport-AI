"""Admin/demo dashboard (section 24)."""
from __future__ import annotations

import streamlit as st

from database.database import dashboard_stats, list_reports
from ui.components import brand_header, go_to


def render():
    brand_header(show_tagline=False)
    st.markdown("## 📊 Admin Dashboard")
    st.caption("Hackathon demo view — shows what has been submitted to the demo backend.")

    stats = dashboard_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Reports", stats["total"])
    c2.metric("Open Reports", stats["open"])
    c3.metric("Submitted", stats["submitted"])

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Reports by Crime Type**")
        if stats["by_type"]:
            st.bar_chart(stats["by_type"])
        else:
            st.caption("No data yet.")
    with col2:
        st.markdown("**Reports by Date**")
        if stats["by_date"]:
            st.bar_chart(stats["by_date"])
        else:
            st.caption("No data yet.")

    st.write("")
    st.markdown("**Recent Reports**")
    reports = list_reports(limit=25)
    if reports:
        st.dataframe(
            [{"Report ID": r["report_id"], "Crime Type": r.get("crime_type") or "Unclassified",
              "Date": r["created_at"][:10], "Status": r["status"]} for r in reports],
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("No reports submitted yet in this demo instance.")

    st.write("")
    if st.button("⬅️ Back to Home", use_container_width=True):
        go_to("home")
