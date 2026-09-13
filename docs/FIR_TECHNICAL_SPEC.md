# Technical Spec — Pakistan FIR-Assist Flow

Status: **draft for review** — extends Crime Report.AI into the Step 0–9 FIR
(First Information Report) drafting flow. Architecture decisions locked in:
stay single-process Streamlit (no separate REST API yet, but every step is
written as a standalone "service" function so a future FastAPI layer is a
thin wrapper, not a rewrite); legal citations come from a **curated RAG
knowledge base**, never from an LLM's parametric memory.

> ⚠️ **Legal accuracy disclaimer for this document itself**: the section
> numbers, punishment ranges, and cognizable/bailable statuses below were
> drafted from web research (see Source column) and are **not verified by a
> lawyer**. Treat every row in §3.2 as a first draft. Before this ships to a
> real user, a qualified lawyer must check each entry against the primary
> source PDFs cited, and against Schedule II of the Code of Criminal
> Procedure, 1898 (which — not the PPC itself — is what actually classifies
> offenses as cognizable/bailable).

---

## 1. Scope change from the current MVP

| Current MVP | This spec |
|---|---|
| Generic international audience | Pakistan-specific (Sindh Police framing, CNIC, PPC/PECA, Urdu-ready copy later) |
| AI classifies category *after* free text | User picks category *first* (Step 1), AI classification becomes a confirmation/override signal instead of the primary driver |
| RAG = general reporting guidance | Two RAG stores: general guidance (existing) **and** legal citations (new, higher accuracy bar) |
| Emergency number generic (`911`, configurable) | Default `EMERGENCY_NUMBER=15` (Police Helpline), same config mechanism |
| No formal document output | Formal FIR-draft PDF referencing specific PPC/PECA sections |
| No PII beyond name/phone/email | Adds CNIC — a national ID number — requiring field-level encryption and stricter access control |
| Single confirm-and-submit step | Two explicit confirmations: false-reporting notice ack + accuracy consent, each timestamped |

Everything below is additive to the existing modules
(`ai/`, `rag/`, `input/`, `reports/`, `database/`, `ui/`) — nothing already
built needs to be thrown away.

---

## 2. Screen flow (Steps 0–9 → pages)

```
Entry (logo/link)
  │
  ▼
Step 0  ui/emergency_check.py   "Is this happening right now / are you in danger?"
  │  Yes → surfaces tel:15 tap-to-call + "Continue reporting anyway" (reuses
  │        existing ui/emergency.py "silent report" pattern)
  │  No  → continue
  ▼
Step 1  ui/category_select.py   8 tappable categories (incl. "Other" free text)
  │        Robbery/Theft · Kidnapping · Assault · Cybercrime/Online Fraud ·
  │        Harassment · Domestic Violence · Vehicle Theft · Other
  ▼
Step 2  ui/report.py (existing) Text / voice / photo / video — unchanged,
  │        but now conditioned on the chosen category (skips re-asking "what
  │        kind of incident" since Step 1 already answered it)
  ▼
Step 3  ui/questionnaire.py (existing engine, extended) — category-specific
  │        required fields (what/when/where/who/suspect description/
  │        witnesses/losses/injuries) layered under the existing dynamic
  │        AI engine as a "must-cover" checklist per category
  ▼
Step 4  ui/legal_lookup.py (new) — "ℹ️ Info" button, reachable from Step 3
  │        onward once a category is set. RAG query against the *legal*
  │        knowledge base → PPC/PECA section(s), cognizable/bailable,
  │        punishment range, "informational only" disclaimer every time.
  ▼
Step 5  ui/summary_form.py (new; supersedes plain review for this flow) —
  │        auto-compiled from Steps 1–3, every field editable inline
  ▼
Step 6  ui/false_reporting_notice.py (new) — shows PPC 182 (false
  │        information to a public servant) notice, requires an explicit
  │        checkbox before proceeding (separate from the accuracy consent
  │        already in Step 7)
  ▼
Step 7  ui/reporter_info.py (new; supersedes the victim-info half of
  │        evidence.py for this flow) — Name, CNIC, phone, address;
  │        CNIC is field-level encrypted at rest (§4.4)
  ▼
Step 8  ui/fir_generator.py (new) — renders the formatted FIR draft PDF,
  │        citing the exact legal_reference rows shown in Step 4
  ▼
Step 9  ui/share_store.py (new; supersedes submitted.py for this flow) —
           download/email/share the FIR PDF; **explicit, unmissable copy**
           stating this is a "bring this to the station" document, not a
           live e-FIR submission (no real Sindh Police API is integrated —
           same demo-backend honesty principle as config.settings.AUTHORITIES)
```

Session-state additions (`ui/state.py`): `is_emergency`, `category`
(user-selected, separate from `draft["crime_type"]` which stays the
AI-inferred confirmation signal), `legal_references` (list, populated by
Step 4), `false_reporting_ack` (bool + timestamp), `reporter` (extends
existing `victim` dict with `cnic`).

---

## 3. Data model

SQLite for the demo (as today), with a migration note to Postgres +
row-level encryption for a real deployment (§4.4). All tables extend
`database/database.py`.

### 3.1 Tables

```sql
-- Existing `reports` table stays, extended with:
ALTER TABLE reports ADD COLUMN category TEXT;           -- Step 1 user-selected
ALTER TABLE reports ADD COLUMN is_emergency INTEGER;     -- Step 0 answer
ALTER TABLE reports ADD COLUMN reporter_cnic_enc BLOB;   -- encrypted, see §4.4
ALTER TABLE reports ADD COLUMN false_reporting_ack_at TEXT;
ALTER TABLE reports ADD COLUMN accuracy_confirmed_at TEXT;

CREATE TABLE legal_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    statute TEXT NOT NULL,          -- "PPC" | "PECA 2016" | "Sindh DV Act 2013"
    section_number TEXT NOT NULL,   -- e.g. "379", "24"
    section_title TEXT,
    cognizable TEXT,                -- "cognizable" | "non-cognizable" | "unknown"
    bailable TEXT,                  -- "bailable" | "non-bailable" | "unknown"
    punishment_range TEXT,
    source_citation TEXT NOT NULL,  -- URL/document the RAG chunk came from
    retrieved_at TEXT NOT NULL,
    disclaimer_shown INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE fir_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    version INTEGER NOT NULL DEFAULT 1,
    pdf_path TEXT NOT NULL,
    template_version TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    confirmation_type TEXT NOT NULL,  -- "false_reporting_notice" | "accuracy_consent"
    confirmed_at TEXT NOT NULL
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT REFERENCES reports(report_id),
    actor TEXT NOT NULL,       -- "user" | "system" | future admin identifier
    action TEXT NOT NULL,      -- "viewed", "exported_pdf", "cnic_decrypted", ...
    details TEXT,              -- JSON
    occurred_at TEXT NOT NULL
);
```

Every read of a `Domestic Violence` or `Harassment` category report should
write an `audit_log` row (§4.4) — these categories carry real personal-safety
risk if the record leaks or is browsed casually.

### 3.2 Legal reference draft mapping (seed data for the legal KB — UNVERIFIED)

| Category | Statute | Section(s) | Cognizable/Bailable (draft) | Source |
|---|---|---|---|---|
| Robbery/Theft | PPC | 379 (theft), 390/392 (robbery) | Theft: bailable · Robbery: non-bailable (draft) | [PPC full text (UNODC)](https://www.unodc.org/cld/uploads/res/document/pak/1860/pakistan_penal_code_1860_html/Pakistan_Penal_Code_1860_incorporating_amendments_to_16_February_2017.pdf) |
| Vehicle Theft | PPC | 379/380 (theft, incl. from a vehicle) | Draft: bailable for simple theft | same as above |
| Kidnapping | PPC | 359–365 (kidnapping/abduction, aggravating circumstances) | Draft: non-bailable for aggravated forms | [UNODC Sherloc §359-365A](https://sherloc.unodc.org/cld/en/legislation/pak/pakistan_penal_code_1860/chapter_xvi-a/sections_359365a_367_368/sections_359365a_367_368.html) |
| Assault | PPC | 351 (assault), 337/338 (hurt, graded) | Varies by hurt category — needs Schedule II lookup | PPC full text |
| Cybercrime/Online Fraud | PECA 2016 | 13/14 (electronic forgery/fraud), 20/21 (dignity/modesty), 24 (cyber stalking) | §21 is cognizable & non-bailable; most others non-cognizable & bailable (draft) | [PECA 2016 full text](https://sja.gos.pk/assets/Acts_Ordinances_Rules2/PEC2016.pdf) |
| Harassment | PPC | 509 (insulting modesty), 504/506 (intimidation) | Draft: bailable | [PPC §506 (UNODC)](https://www.unodc.org/cld/en/legislation/pak/pakistan_penal_code_1860/chapter_xxii/section_506/section_506.html) |
| Domestic Violence | Sindh Domestic Violence (Prevention & Protection) Act, 2013 | Protection order + breach provisions | Breach of protection order: cognizable, bailable, compoundable (draft) | [Sindh Act XX of 2013 (official)](https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-18-000141.pdf) |
| False reporting notice (Step 6, all categories) | PPC | 182 (false information to a public servant) | — | [PPC §182 text](http://www.pljlawsite.com/html/ppc182.htm) |

This table is the seed content for `knowledge_base/legal/*.txt` — written up
as short, cited paragraphs (same chunk-and-embed pipeline as the existing
`knowledge_base/crimes/*.txt`), ingested into a **separate Pinecone
namespace** (`legal`) so a Step 4 lookup never accidentally mixes in general
reporting-guidance text. `rag/ingest.py` already supports per-category
metadata filtering — this only needs a `namespace="legal"` parameter added
to `upsert_vectors`/`query`.

---

## 4. "API-shaped" service layer

No HTTP server yet (per your call to stay in Streamlit), but every step gets
one function with a signature that would translate 1:1 to a REST endpoint
later. New `services/` package; UI pages become thin — they call a service
function and render its return value, nothing else.

### 4.1 Service functions → future REST mapping

| Service function | Future endpoint | Notes |
|---|---|---|
| `incident_service.start_incident(is_emergency: bool, category: str) -> str` | `POST /incidents` | Returns `report_id` (draft, pre-confirmation) |
| `incident_service.update_description(report_id, text, methods_used) -> None` | `PATCH /incidents/{id}` | Step 2 |
| `evidence_service.add_evidence(report_id, file_bytes, filename, kind) -> dict` | `POST /incidents/{id}/evidence` | Wraps existing `input/image.py`, `input/video.py` |
| `questionnaire_service.next_question(report_id) -> Question \| None` | `GET /incidents/{id}/next-question` | Wraps existing `ai/question_engine.py`, adds the category checklist |
| `questionnaire_service.submit_answer(report_id, question, answer) -> None` | `POST /incidents/{id}/answers` | |
| `legal_service.lookup(report_id) -> list[LegalReference]` | `GET /incidents/{id}/legal-references` | RAG against the `legal` namespace; persists rows into `legal_references` |
| `confirmation_service.acknowledge(report_id, kind: Literal["false_reporting_notice","accuracy_consent"]) -> str` | `POST /incidents/{id}/confirmations` | Returns timestamp; both required before Step 8 |
| `reporter_service.save(report_id, name, cnic, phone, address) -> None` | `POST /incidents/{id}/reporter` | Encrypts CNIC before write (§4.4) |
| `fir_service.generate(report_id) -> bytes` | `POST /incidents/{id}/fir` | New PDF template in `reports/fir_template.py`, sibling to `reports/generator.py` |
| `share_service.export(report_id, method: Literal["download","email"]) -> dict` | `POST /incidents/{id}/share` | Email is a v2 feature — needs an SMTP/provider decision, not in scope yet |

### 4.2 Auth (deferred, noted for later)

Today: no auth, Streamlit session = the "session" (as now). If/when this
becomes a real multi-user deployment with actual identity verification, plan
for: phone-number OTP at Step 7 (before CNIC is accepted) + short-lived JWT
per session, since a document resembling an FIR should not be attachable to
an unverified phone number. **Not building this now** — flagging it so the
`reporter_service.save` signature above already takes a verified-phone
parameter placeholder when that lands.

### 4.3 Category checklist (Step 3 "must-cover" fields)

Layered on top of the existing dynamic engine (`ai/question_engine.py`)
rather than replacing it — the checklist guarantees the spec's what/when/
where/who/suspect/witnesses/losses-injuries are always asked at least once
per category, while the LLM still decides ordering, phrasing, and any
category-specific extras (RAG-informed as today).

```python
# config/settings.py addition
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
```

`questionnaire_service.next_question` cross-checks `known_facts` +
`qa_history` against this list before asking the LLM for the next question,
and passes any still-missing required fields into the existing
`missing_information` mechanism the engine already has.

### 4.4 Security & privacy (CNIC-specific)

- **Field-level encryption**: new `security/encryption.py` using
  `cryptography.Fernet` (symmetric, simple, adequate for a hackathon-to-early-
  production step). Key comes from `FIELD_ENCRYPTION_KEY` in `.env` (never
  hard-coded, never committed — same pattern as every other secret in this
  project). CNIC is encrypted before `INSERT`, decrypted only inside
  `reporter_service` when rendering the FIR PDF or showing it back to the
  same session — every decrypt call writes an `audit_log` row.
- **Sensitive categories** (`Domestic Violence`, `Harassment`): any read of
  a report row in these categories goes through
  `database.database.get_report_audited(report_id, actor)` instead of the
  plain `get_report` — same query, plus an `audit_log` write. The
  `dashboard.py` aggregate counts stay category-blind (counts only, no
  content) so the admin dashboard doesn't become a way to browse sensitive
  reports.
- **Production note**: SQLite + Fernet is a reasonable hackathon-grade
  answer. A real deployment should move to Postgres with encrypted columns
  (or full-disk/tablespace encryption) and a managed secrets store (not a
  `.env` file) for `FIELD_ENCRYPTION_KEY` — flagged here so it isn't
  forgotten, not being built now.

---

## 5. Implementation phases (suggested order)

1. **Category restructure**: replace `CRIME_CATEGORIES` with the Step 1
   list, add `CATEGORY_REQUIRED_FIELDS`, add `ui/category_select.py`,
   rewire `ui/report.py` to take the category as a given rather than
   inferring it from scratch.
2. **Legal RAG subsystem**: `knowledge_base/legal/*.txt` (seeded from §3.2,
   clearly marked draft), `legal` Pinecone namespace, `legal_service.py`,
   `ui/legal_lookup.py`. Ships with a visible "⚠️ unverified — pending legal
   review" badge until you confirm the content has been checked.
3. **Step 0 emergency gate + Step 6 false-reporting notice**: both are
   mostly copy + a confirmation checkbox, low engineering risk.
4. **Reporter info + CNIC encryption**: `security/encryption.py`,
   `reporter_service.py`, schema migration for `reporter_cnic_enc`.
5. **FIR PDF template**: `reports/fir_template.py`, referencing
   `legal_references` rows, with the "bring this to the station" disclaimer
   printed on every page.
6. **Audit log + sensitive-category access wrapper.**

Each phase is independently shippable and testable against the existing
offline test suite pattern (`tests/`).

---

## 6. Open questions for you

1. Do you have (or can you get) a lawyer to review §3.2 before this goes in
   front of real users, even in demo form? I'd rather the app under-claim
   ("see a lawyer") than state a wrong section/punishment with confidence.
2. Should Step 1's category list fully replace the current
   `CRIME_CATEGORIES`, or should the AI classifier still map free text onto
   this same list as a fallback for the "Other" category?
3. For Step 9 "share" — download/PDF is in scope now; is email sharing
   something you want in this phase, or later (it needs an SMTP/provider
   decision I haven't made)?
