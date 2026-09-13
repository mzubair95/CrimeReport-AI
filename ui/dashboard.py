"""
Reviewer/Admin Dashboard (PRD §5 "Authorized Reviewer" / "Supervisor,
Analyst" + P1 "Reviewer dashboard": list, filters, case details, AI summary).
Demo-only: no real authentication gates this in the hackathon MVP, but the
review-action audit trail (FR-10) is real.
"""
from __future__ import annotations

import streamlit as st

from config.settings import CRIME_CATEGORIES, SEVERITY_LEVELS, CASE_STATUSES
from database.database import dashboard_stats, list_reports, get_report, update_status
from ui.components import brand_header, go_to, card


def render():
    brand_header(show_tagline=False)
    st.markdown("## 📊 Reviewer Dashboard")
    st.caption("Hackathon demo view — no real authentication gates this reviewer role yet.")

    stats = dashboard_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Reports", stats["total"])
    c2.metric("Open (not Resolved/Closed)", stats["open"])
    c3.metric("Critical + High Priority",
              stats["by_severity"].get("Critical", 0) + stats["by_severity"].get("High", 0))

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Reports by Category**")
        if stats["by_category"]:
            st.bar_chart(stats["by_category"])
        else:
            st.caption("No data yet.")
    with col2:
        st.markdown("**Reports by Priority**")
        if stats["by_severity"]:
            st.bar_chart(stats["by_severity"])
        else:
            st.caption("No data yet.")

    st.markdown("**Reports by Date**")
    if stats["by_date"]:
        st.bar_chart(stats["by_date"])
    else:
        st.caption("No data yet.")

    st.divider()
    st.markdown("### Case Queue")

    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        category_filter = st.selectbox("Category", ["All"] + CRIME_CATEGORIES)
    with fcol2:
        severity_filter = st.selectbox("Priority", ["All"] + SEVERITY_LEVELS)
    with fcol3:
        status_filter = st.selectbox("Status", ["All"] + CASE_STATUSES)

    reports = list_reports(
        category=None if category_filter == "All" else category_filter,
        severity=None if severity_filter == "All" else severity_filter,
        status=None if status_filter == "All" else status_filter,
    )

    if not reports:
        st.caption("No reports match these filters.")
    else:
        st.dataframe(
            [{"Case ID": r["report_id"], "Category": r.get("category") or "Unclassified",
              "Priority": r.get("severity") or "—", "Status": r["status"],
              "Flags": len(r.get("verification_flags") or []),
              "Date": r["created_at"][:10]} for r in reports],
            use_container_width=True, hide_index=True,
        )

        selected_id = st.selectbox("Open a case", [r["report_id"] for r in reports])
        if selected_id:
            _render_case_detail(selected_id)

    st.write("")
    if st.button("⬅️ Back to Home", use_container_width=True):
        go_to("home")


def _render_case_detail(report_id: str):
    report = get_report(report_id)
    if not report:
        return

    st.write("")
    card(f"""
        <b>Case {report['report_id']}</b><br>
        Category: {report.get('category') or 'Unclassified'}<br>
        Priority: <b>{report.get('severity') or 'Not assessed'}</b> — {report.get('severity_reason', '')}<br>
        Status: {report['status']}<br>
        Language: {report.get('language') or 'English'}<br>
        Reporter: {"Anonymous" if report.get('anonymous') else (report.get('reporter', {}).get('full_name') or 'N/A')}
    """)

    st.markdown("**AI Summary**")
    st.write(report.get("summary") or "N/A")

    with st.expander("Original description"):
        st.write(report.get("description") or "N/A")

    if report.get("qa_history"):
        with st.expander(f"Follow-up answers ({len(report['qa_history'])})"):
            for qa in report["qa_history"]:
                st.markdown(f"**{qa['question']}** — {qa['answer']}")

    flags = report.get("verification_flags") or []
    if flags:
        st.markdown("**🔎 Verification flags**")
        for f in flags:
            st.markdown(f"- **{f['flag_type'].replace('_', ' ').title()}**: {f['message']}")

    related = report.get("related_incidents") or []
    if related:
        st.markdown("**🔁 Related/possible duplicate reports**")
        for r in related:
            st.markdown(f"- `{r['related_report_id']}` (similarity {r['similarity_score']:.0%}) — {r.get('reason', '')}")

    evidence = report.get("evidence") or []
    if evidence:
        st.markdown(f"**Evidence** ({len(evidence)} file(s))")
        for e in evidence:
            st.markdown(f"- {e.get('name')} ({e.get('type')}): {e.get('ai_analysis', '')}")
            for flag in e.get("privacy_flags", []):
                st.caption(f"🔒 {flag}")

    actions = report.get("review_actions") or []
    if actions:
        with st.expander(f"Review action log ({len(actions)})"):
            for a in actions:
                st.caption(f"{a['occurred_at'][:19]} — {a['reviewer_id']}: {a['action']} {a.get('note', '')}")

    st.markdown("**Update status**")
    col1, col2 = st.columns([2, 1])
    with col1:
        new_status = st.selectbox("New status", CASE_STATUSES,
                                   index=CASE_STATUSES.index(report["status"])
                                   if report["status"] in CASE_STATUSES else 0,
                                   key=f"status_{report_id}")
        note = st.text_input("Note (optional)", key=f"note_{report_id}")
    with col2:
        st.write("")
        st.write("")
        if st.button("Update", key=f"update_{report_id}", use_container_width=True):
            update_status(report_id, new_status, reviewer_id="demo-reviewer", note=note)
            st.success(f"Status updated to {new_status}")
            st.rerun()
