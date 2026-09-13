# Technical Spec — Pakistan FIR-Assist Flow

Status: **implemented** — all 6 phases in §5 are built and verified live
end-to-end against the real Groq + Pinecone backend. Architecture decisions:
single-process Streamlit (no separate REST API, but every step is a
standalone "service"/module function so a future FastAPI layer is a thin
wrapper, not a rewrite); legal citations come from a **curated RAG
knowledge base**, never from an LLM's parametric memory, and as of
2026-09-13 that knowledge base has been through an AI-assisted verification
pass against primary-source statute text (see §3.2's note on what remains
unconfirmed).

> ⚠️ **Legal accuracy disclaimer for this document itself**: §3.2 has been
> through an **AI-assisted verification pass** (2026-09-13) — every section
> number, punishment figure, and PECA/Sindh-DV-Act cognizable/bailable
> classification below was checked against the actual primary-source
> statute PDF text (not a secondary summary), and corrections were made
> where the original draft was wrong (see §3.2 notes). This materially
> improves confidence over the first draft, but it is still **not a
> substitute for a qualified lawyer**: (a) it was done by an AI assistant,
> not a licensed advocate; (b) the cognizable/bailable status of the *plain
> PPC* sections (theft, robbery, kidnapping, assault, harassment, false
> reporting) could not be independently confirmed — that classification
> comes from Schedule II of the Code of Criminal Procedure, 1898, and the
> two Schedule II source documents fetched during this pass did not yield
> extractable table text; those fields are marked "commonly cited... not
> independently confirmed" rather than asserted as fact; (c) the PPC 337/338
> "hurt" grading (relevant to Assault) genuinely requires a medico-legal
> assessment per case, not a lookup. Before this ships to a real user, a
> qualified lawyer should still review §3.2, with priority on confirming
> Schedule II status for the PPC entries.

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

### 3.2 Legal reference mapping — AI-assisted verification pass (2026-09-13)

| Category | Statute | Section(s) | Punishment (verified against primary text) | Cognizable/Bailable | Source |
|---|---|---|---|---|---|
| Robbery/Theft | PPC | 379 (theft), 380 (theft in dwelling), 390 (robbery def.), 392 (robbery punishment) | 379: up to 3yr/fine/both · 380: up to 7yr+fine · 392: rigorous 3–10yr+fine (up to 14yr on highway) | Not independently confirmed against Schedule II (commonly cited: theft bailable, robbery non-bailable) | [PPC full text](https://sherloc.unodc.org/cld/uploads/res/document/pak/1860/pakistan_penal_code_1860_html/Pakistan_Penal_Code_1860_incorporating_amendments_to_16_February_2017.pdf), [§379](http://www.pljlawsite.com/html/ppc379.htm), [§380](http://www.pljlawsite.com/html/ppc380.htm), [§390](http://www.pljlawsite.com/html/ppc390.htm), [§392](http://www.pljlawsite.com/html/ppc392.htm) |
| Vehicle Theft | PPC | 379 / 380 (same as above, no standalone vehicle-theft offense in the PPC) | Same as above | Same as above | Same as above |
| Kidnapping | PPC | 359 (def.), 363 (base punishment), 364 (to murder), 365 (to confine), 365-A (for ransom/extortion) | 363: up to 7yr+fine · 364: life or up to 10yr+fine · 365: up to 7yr+fine · 365-A: death or life imprisonment | Not independently confirmed against Schedule II | [§359](http://www.pljlawsite.com/html/ppc359.htm), [§363](http://www.pljlawsite.com/html/ppc363.htm), [§364](http://www.pljlawsite.com/html/ppc364.htm), [§365](http://www.pljlawsite.com/html/ppc365.htm), [§365-A](http://www.pljlawsite.com/html/ppc365a.htm) |
| Assault | PPC | 351 (def.), 352 (base punishment) | 352: up to 3mo or fine up to PKR 1,500, or both | Not independently confirmed against Schedule II | [§351](http://www.pljlawsite.com/html/ppc351.htm), [§352](http://www.pljlawsite.com/html/ppc352.htm) |
| Assault (hurt) | PPC | 337 (Shajjah — head/face injury grading only) | **Not resolved** — the hurt framework spans many further lettered sub-sections not individually verified; exact classification needs a doctor + lawyer, not a lookup. **Correction**: §338 is *not* a hurt provision — it defines Isqat-i-Haml (miscarriage), unrelated to assault. An earlier draft of this table incorrectly grouped 337/338 together. | Varies by sub-clause, not verified | [§337](http://www.pljlawsite.com/html/ppc337.htm), [§338](http://www.pljlawsite.com/html/ppc338.htm) |
| Cybercrime/Online Fraud | PECA 2016 | 13 (electronic forgery), 14 (electronic fraud), 24 (cyber stalking) | 13: up to 3yr/PKR 250k/both (up to 7yr/PKR 5M for critical infrastructure) · 14: up to 2yr/PKR 10M/both · 24: up to 3yr/PKR 1M/both (up to 5yr/PKR 10M if victim is a minor) | **Verified**: non-cognizable, bailable, compoundable (PECA §43(1) — the Act's default for everything except §§10/21/22) | [PECA 2016 full text](https://sja.gos.pk/assets/Acts_Ordinances_Rules2/PEC2016.pdf) §§13, 14, 24, 43 |
| Harassment | PECA 2016 | 20 (dignity), 21 (modesty/minor) | 20: up to 3yr/PKR 1M/both · 21 base: up to 5yr/PKR 5M/both; if minor: up to 7yr/PKR 5M (10yr flat if repeat offence against a minor) | **Verified**: §20 non-cognizable/bailable; §21 is one of only 3 PECA sections (10/21/22) that is **cognizable and non-bailable** (PECA §43(2)) | Same PECA source, §§20, 21, 43 |
| Harassment | PPC | 509 (insulting modesty), 504 (intentional insult), 506 (criminal intimidation) | 509: up to 3yr or fine up to PKR 500,000, or both · 504: up to 2yr/fine/both · 506 base: up to 2yr/fine/both, aggravated (death/grievous hurt/fire/imputing unchastity threats): up to 7yr/fine/both | Not independently confirmed against Schedule II | [§509 text](https://pakarbiter.com/laws-in-pakistan/pakistan-penal-code-1860/ppc-section-509/insulting-modesty-or-causing-sexual-harrassment), [§504](http://www.pljlawsite.com/html/ppc504.htm), [§506](http://www.pljlawsite.com/html/ppc506.htm) |
| Domestic Violence | Sindh Domestic Violence (Prevention & Protection) Act, 2013 | §15 (breach of protection order), §6 (punishment for underlying §5 offenses) | §15: up to 1yr or fine up to PKR 20,000, or both · §6: sub-clause-specific (5(f): min 6mo/PKR 10k+; 5(k) stalking: min 1yr/PKR 20k+; 5(l): min 2yr/PKR 50k+; 5(m): min 1mo) | **Verified**: §15(2) explicitly states the breach offense "shall be cognizable, bailable and compoundable" — an explicit statutory override of the default CrPC classification | [Sindh Act XX of 2013 (official)](https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-18-000141.pdf) §§6, 15 |
| False reporting notice (Step 6, all categories) | PPC | 182 (false information to a public servant) | Base: up to 6mo or fine. Escalates with the severity of the falsely-alleged offense: up to 7yr if that offense carries death, up to 5yr if life imprisonment, else up to 1/4 of its longest term. | Not independently confirmed against Schedule II (commonly cited as bailable) | [PPC §182 text](http://www.pljlawsite.com/html/ppc182.htm) |

**What "verified" means here**: for PECA 2016 and the Sindh Domestic Violence
Act, the cognizable/bailable classification is stated *in the statute
itself* (PECA §43, Sindh Act §15(2)), so fetching and reading the primary
PDF text directly confirms it. For the plain PPC sections, cognizable/
bailable status comes from a *separate* document (CrPC Schedule II) that
this pass could not get clean extractable text from (two different PDF
sources were tried) — those cells say "not independently confirmed" rather
than stating a number with false confidence. Punishment figures for PPC
sections were confirmed against primary section text directly and are
higher-confidence than the cognizable/bailable classification.

This table is the seed content for
`knowledge_base/legal/legal_references.json` — one structured JSON record
per section (not chunked prose), ingested into a **separate Pinecone
namespace** (`legal`) so a Step 4 lookup never accidentally mixes in general
reporting-guidance text, and always filtered by exact category (never
similarity-only), so a lookup can never surface a different category's
statute.

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

1. ✅ **Category restructure**: `CRIME_CATEGORIES` replaced with the Step 1
   list, `CATEGORY_REQUIRED_FIELDS` added, `ui/category_select.py` built,
   `ui/report.py` takes the category as a given.
2. ✅ **Legal RAG subsystem**: `knowledge_base/legal/legal_references.json`
   (seeded from §3.2 — as of 2026-09-13, AI-assisted-verified against
   primary-source statute text; Schedule II cognizable/bailable status for
   plain PPC sections still not independently confirmed), `legal` Pinecone
   namespace, `legal_service.py`, `ui/legal_lookup.py`. The in-app
   disclaimer (`ai/legal_service.DISCLAIMER`) still tells users this is not
   legal advice and has not been reviewed by a lawyer, regardless of the
   verification pass.
3. ✅ **Step 0 emergency gate + Step 6 false-reporting notice**:
   `ui/emergency_check.py` and `ui/false_reporting_notice.py` built, the
   PPC 182 notice pulled via exact metadata match with a hard-coded
   fallback so it can never fail to render.
4. ✅ **Reporter info + CNIC encryption**: `security/encryption.py`
   (Fernet), CNIC field added to `ui/evidence.py`'s reporter form,
   `reporter_cnic_enc` column, `decrypt_cnic()` with mandatory audit
   logging.
5. ✅ **FIR PDF template**: `reports/fir_template.py`, referencing
   `legal_references` rows, with the "bring this to the station" disclaimer
   printed on every page; `fir_documents` table tracks generated versions.
6. ✅ **Audit log + sensitive-category access wrapper**: `audit_log` table,
   `get_report_audited()`, wired into `ui/status.py`.

All 6 phases were verified live end-to-end (not just unit-tested) and are
covered by the offline test suite (`tests/`).

---

## 6. Open questions for you

1. ~~Do you have (or can you get) a lawyer to review §3.2?~~ **Partially
   addressed 2026-09-13**: an AI-assisted pass verified every punishment
   figure and the PECA/Sindh-DV-Act cognizable/bailable status against
   primary source text (not secondary summaries), and corrected a real
   error (337/338 were wrongly grouped as one "hurt" provision — 338 is
   actually an unrelated miscarriage offense). What's still open: the
   cognizable/bailable status of the *plain PPC* sections couldn't be
   confirmed against CrPC Schedule II (two source PDFs didn't yield
   extractable table text), and the PPC 337-series hurt grading needs a
   case-by-case medico-legal read that no lookup can replace. **A qualified
   lawyer should still review §3.2** before this goes in front of real
   users — the bar has moved from "unverified web research" to "AI-verified
   against primary text, still not lawyer-reviewed," which is better but
   not the same thing.
2. Should Step 1's category list fully replace the current
   `CRIME_CATEGORIES`, or should the AI classifier still map free text onto
   this same list as a fallback for the "Other" category? **Resolved**:
   the Step 1 list replaced `CRIME_CATEGORIES` outright; the AI classifier
   now runs as a confirmation/override signal against the user's pick
   rather than a parallel list.
3. For Step 9 "share" — download/PDF is in scope now; is email sharing
   something you want in this phase, or later (it needs an SMTP/provider
   decision I haven't made)? **Still open** — not built.
