"""
Central configuration. Everything secret comes from environment variables
(loaded from .env via python-dotenv), never hard-coded.

Aligned to the "Crime Report" PRD (Pak Angels hackathon) — a citizen
incident-reporting + AI triage/verification platform, not a legal-document
generator. See README.md for the product summary.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ---- Secrets / API config (never hard-code these) ----
# Which LLM backend powers classification/questions/summaries/vision (the LLM
# must be swappable without rewriting the app). "gemini" (default), "grok"
# (xAI), or "groq" (Groq's fast-inference open-model hosting — note this is a
# different company from Grok/xAI despite the near-identical name).
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

# Local, free, offline speech-to-text for voice input — kept independent of
# whichever LLM_PROVIDER is chosen, since not every LLM API accepts raw
# audio the way Gemini does. "" disables transcription gracefully.
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")

# ---- App-level config ----
APP_NAME = "Crime Report"
APP_TAGLINE = "Report. Understand. Prioritize. Respond."

DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
REPORTS_DIR = DATA_DIR / "reports"
DB_DIR = DATA_DIR / "db"
for _d in (DATA_DIR, UPLOADS_DIR, REPORTS_DIR, DB_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "crime_report.sqlite3"

# Incident categories (PRD §10).
CRIME_CATEGORIES = [
    "Theft / Pickpocketing", "Robbery", "Vehicle Theft", "Assault / Physical Harm",
    "Harassment", "Domestic / Family Safety", "Fraud / Scam", "Cybercrime",
    "Missing Person", "Vandalism / Property Damage", "Suspicious Activity",
    "Drug-related Incident", "Other / Unclassified",
]

# Severity / triage levels (PRD §11), most severe first.
SEVERITY_LEVELS = ["Critical", "High", "Medium", "Low"]
SEVERITY_MEANING = {
    "Critical": "Potential immediate threat to life or safety",
    "High": "Serious incident needing quick attention",
    "Medium": "Investigation/review required",
    "Low": "Non-urgent or informational",
}

# Case status workflow (PRD §8/§12 "Case tracking").
CASE_STATUSES = ["Submitted", "Under Review", "Assigned", "Resolved", "Closed"]

# Supported reporting languages (PRD FR-03, "Must" for the MVP).
SUPPORTED_LANGUAGES = ["English", "Urdu", "Roman Urdu"]

# Category-specific "must eventually cover" fields, layered on top of the
# dynamic AI questionnaire as coverage guidance (never a rigid fixed form).
# Kept generic per PRD's structured-report fields (time, location, objects,
# people count, narrative) rather than any jurisdiction-specific checklist.
_BASE_FIELDS = ["when", "where", "narrative_detail", "people_involved_count", "objects_involved"]
CATEGORY_REQUIRED_FIELDS = {
    "Theft / Pickpocketing": _BASE_FIELDS + ["items_taken", "suspect_description"],
    "Robbery": _BASE_FIELDS + ["items_taken", "suspect_description", "weapon_involved"],
    "Vehicle Theft": _BASE_FIELDS + ["vehicle_details", "registration_number"],
    "Assault / Physical Harm": _BASE_FIELDS + ["injuries", "relationship_to_suspect"],
    "Harassment": _BASE_FIELDS + ["nature_of_contact", "frequency", "relationship_to_suspect"],
    "Domestic / Family Safety": _BASE_FIELDS + ["relationship_to_suspect", "injuries", "immediate_safety_risk"],
    "Fraud / Scam": _BASE_FIELDS + ["method_used", "financial_loss"],
    "Cybercrime": _BASE_FIELDS + ["platform_or_account", "financial_loss", "evidence_saved"],
    "Missing Person": _BASE_FIELDS + ["physical_description", "last_seen_details"],
    "Vandalism / Property Damage": _BASE_FIELDS + ["property_damaged", "estimated_cost"],
    "Suspicious Activity": _BASE_FIELDS + ["activity_description", "suspect_description"],
    "Drug-related Incident": _BASE_FIELDS + ["substance_description"],
    "Other / Unclassified": _BASE_FIELDS,
}

# Configurable emergency numbers (demo-labeled; NOT a real dispatch integration).
EMERGENCY_NUMBER = os.getenv("EMERGENCY_NUMBER", "15")

DISCLAIMER = (
    "Crime Report provides AI-assisted reporting support. AI-generated "
    "classifications, priority levels, and verification flags may contain "
    "errors and are reviewed by an authorized human reviewer before any "
    "action is taken. The application does not replace emergency services "
    "or law enforcement, and does not determine guilt, innocence, or legal "
    "liability."
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
