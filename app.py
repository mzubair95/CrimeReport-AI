"""
Crime Report.AI — main Streamlit entry point.

Run with:  streamlit run app.py
"""
import logging

import streamlit as st

from config.settings import APP_NAME
from database.database import init_db
from ui.components import inject_css, top_nav, disclaimer_footer, has_logo, LOGO_PATH
from ui.state import init_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title=APP_NAME, page_icon=str(LOGO_PATH) if has_logo() else "🛡️",
                    layout="centered", initial_sidebar_state="collapsed")

init_db()
init_session()
inject_css()

PAGE_RENDERERS = {}


def _load_pages():
    """Import page modules lazily so a single broken page can't crash routing."""
    from ui import home, emergency, report, questionnaire, evidence, review, submitted, status, dashboard, about
    PAGE_RENDERERS.update({
        "home": home.render,
        "emergency": emergency.render,
        "report": report.render,
        "questionnaire": questionnaire.render,
        "evidence": evidence.render,
        "review": review.render,
        "submitted": submitted.render,
        "status": status.render,
        "dashboard": dashboard.render,
        "about": about.render,
    })


_load_pages()

current_page = st.session_state.get("page", "home")
if current_page not in ("home", "emergency"):
    top_nav(current_page)

renderer = PAGE_RENDERERS.get(current_page, PAGE_RENDERERS["home"])

try:
    renderer()
except Exception:
    logging.getLogger("crime_report_ai.app").exception("Unhandled error rendering page %s", current_page)
    st.error("We're temporarily unable to process this request. "
             "Please try again or return to Home.")
    if st.button("🏠 Back to Home"):
        st.session_state.page = "home"
        st.rerun()

disclaimer_footer()
