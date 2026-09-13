"""
Central configuration. Everything secret comes from environment variables
(loaded from .env via python-dotenv), never hard-coded.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ---- Secrets / API config (never hard-code these) ----
# Which LLM backend powers classification/questions/summaries/vision (section 36:
# the LLM must be swappable without rewriting the app). "gemini" (default),
# "grok" (xAI), or "groq" (Groq's fast-inference open-model hosting — note this
# is a different company from Grok/xAI despite the near-identical name).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")

GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_BASE_URL = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1")
GROK_TEXT_MODEL = os.getenv("GROK_TEXT_MODEL", "grok-4.6")
GROK_VISION_MODEL = os.getenv("GROK_VISION_MODEL", "grok-4.6")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-120b")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "crime-report-ai")

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2 output size; update if provider changes

# Local, free, offline speech-to-text for voice input (section 8/36) — kept
# independent of whichever LLM_PROVIDER is chosen, since not every LLM API
# accepts raw audio the way Gemini does. "" disables transcription gracefully.
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")

# Field-level encryption key for sensitive PII (currently: CNIC) — see
# security/encryption.py and FIR spec §4.4. Generate one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "")

# ---- App-level config ----
APP_NAME = "Crime Report.AI"
APP_TAGLINE = "Report what happened. Let AI guide the rest."

DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
REPORTS_DIR = DATA_DIR / "reports"
DB_DIR = DATA_DIR / "db"
for _d in (DATA_DIR, UPLOADS_DIR, REPORTS_DIR, DB_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "crime_report.sqlite3"

# Controlled classification categories (section 11), aligned to the Step 1
# tappable categories in docs/FIR_TECHNICAL_SPEC.md. The user picks one of
# these first; the AI classifier (ai/classifier.py) then acts as a
# confirmation/override signal rather than the primary driver.
CRIME_CATEGORIES = [
    "Robbery/Theft", "Kidnapping", "Assault", "Cybercrime/Online Fraud",
    "Harassment", "Domestic Violence", "Vehicle Theft", "Other",
]

# Category-specific "must eventually cover" fields (spec §4.3). The dynamic
# questionnaire engine (ai/question_engine.py) passes these to the LLM as
# guidance so the adaptive conversation still reliably covers what/when/
# where/who/suspect/witnesses/losses-injuries per category, without turning
# it into a rigid fixed form.
CATEGORY_REQUIRED_FIELDS = {
    "Robbery/Theft": ["what_taken", "when", "where", "suspect_description", "witnesses", "value_lost"],
    "Kidnapping": ["who_taken", "when", "where_last_seen", "suspect_description", "witnesses", "demands_made"],
    "Assault": ["who_involved", "when", "where", "injuries", "witnesses", "weapon_involved"],
    "Cybercrime/Online Fraud": ["platform_or_account", "when", "financial_loss", "suspect_info", "evidence_saved"],
    "Harassment": ["nature_of_contact", "frequency", "relationship_to_suspect", "witnesses"],
    "Domestic Violence": ["relationship_to_suspect", "when", "injuries", "immediate_safety_risk", "prior_incidents"],
    "Vehicle Theft": ["vehicle_details", "when", "where", "registration_number", "witnesses"],
    "Other": ["what", "when", "where", "who"],
}

# Configurable authority layer (section 12/23) — informational only for the MVP.
# A real deployment would populate each authority's actual submission endpoint.
AUTHORITIES = [
    {
        "id": "demo-local-police",
        "name": "Demo Local Police Department (non-emergency)",
        "handles": ["Robbery/Theft", "Vehicle Theft", "Assault", "Kidnapping", "Other"],
        "integration": "demo",  # "demo" = no real agency is connected
        "contact": "Configure a real non-emergency line in production.",
    },
    {
        "id": "demo-cybercrime-unit",
        "name": "Demo Cybercrime Reporting Unit",
        "handles": ["Cybercrime/Online Fraud", "Harassment"],
        "integration": "demo",
        "contact": "Configure a real cybercrime portal in production.",
    },
    {
        "id": "demo-protection-unit",
        "name": "Demo Women & Children Protection Unit",
        "handles": ["Domestic Violence"],
        "integration": "demo",
        "contact": "Configure the real protection unit in production.",
    },
]

# Configurable emergency numbers (demo-labeled; NOT a real dispatch integration).
# Default is Pakistan's Police Helpline; override via .env for other regions.
EMERGENCY_NUMBER = os.getenv("EMERGENCY_NUMBER", "15")

DISCLAIMER = (
    "Crime Report.AI provides AI-assisted reporting support. AI-generated "
    "information may contain errors and should be reviewed by the user before "
    "submission. The application does not replace emergency services, law "
    "enforcement, legal professionals, or official reporting procedures."
)


def gemini_configured() -> bool:
    return bool(GEMINI_API_KEY)


def grok_configured() -> bool:
    return bool(GROK_API_KEY)


def groq_configured() -> bool:
    return bool(GROQ_API_KEY)


def llm_configured() -> bool:
    if LLM_PROVIDER == "grok":
        return grok_configured()
    if LLM_PROVIDER == "groq":
        return groq_configured()
    return gemini_configured()


def pinecone_configured() -> bool:
    return bool(PINECONE_API_KEY)


def encryption_configured() -> bool:
    return bool(FIELD_ENCRYPTION_KEY)


# Categories that carry real personal-safety risk if their reports are
# browsed casually — any read of one of these goes through the audited
# access path (database.database.get_report_audited) instead of a plain
# lookup (FIR spec §4.4).
SENSITIVE_CATEGORIES = ["Domestic Violence", "Harassment"]
