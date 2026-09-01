# PERSON KB BASE V1

The canonical architecture document for the Person side of МОЖУ / MNP.
Person-side equivalent of the Career KB (`docs/mnp_v1/04_KNOWLEDGE_BASE/`).

## 1. Purpose

**FACT-FIRST career profile.** It answers one question:

> **What do we actually know about this person?**

Education · credentials · experience · activities/projects · skills/tools ·
languages · mobility · supporting documents — with an explicit evidence
state on every fact.

## 2. Non-goals (V1 excludes)

Psychological portrait · personality model · RIASEC · Big Five · Work
Values assessment · Work Styles assessment · aptitude testing · AI
personality inference · universal career-fit score · Knowledge Fit ·
Route Engine V2 · Market KB · salary intelligence · portfolio builder ·
Resume Builder redesign · visual redesign · gamification.

## 3. One canonical Person KB

```
ADMIN MANUAL  ─┐
USER MANUAL   ─┼──▶  MnpPerson  (mnp_persons + fact tables)
USER CV       ─┘
```

There is **one** `MnpPerson`. Not a CV Profile + a User Profile + an Admin
Profile. All three entry flows write the same tables.

Deliberately a **new** root, not the old `MnpCareerCard` (a person-side
profile misnamed "Career Card", wired into the Matching engine + the
resume flow, carrying preference/values scope V1 excludes). Old
architecture disposition — see §14.

## 4. Entities & tables

| table | what |
|---|---|
| `mnp_persons` | root: contact (`first_name` required, everything else optional), location, `date_of_birth`, `status`, `source`, `profile_version`, **mobility columns**, `notes`, `archived_at` |
| `mnp_person_educations` | 0..N — level / institution / specialty / years / `status` (completed/ongoing/incomplete/unknown) |
| `mnp_person_credentials` | 0..N — course / certificate / license / professional_credential / other |
| `mnp_person_experiences` | 0..N — `raw_job_title` (immutable fact) + `canonical_career_id` (separate nullable mapping) + company / dates / `is_current` (tri-state) / responsibilities / achievements / tools |
| `mnp_person_activities` | 0..N — project / academic_project / practice / internship / volunteering / student_activity / student_government / event_organization / pet_project / other — so the KB works for students, graduates, veterans, career changers, returners |
| `mnp_person_skills_v1` | 0..N — `canonical_skill_id` → **`mnp_skills`** (the SAME taxonomy the Career KB uses) OR `raw_input` + `custom_status = pending_review` |
| `mnp_person_languages_v1` | 0..N — language + level (A1..C2 / native / unknown / other) |
| `mnp_person_documents` | 0..N — CV / diploma / certificate / driver_license / recommendation / … ; `storage_ref` opaque path, bytes never in DB |
| `mnp_web_sessions` | bearer session tokens for private user routes — `token_hash` (sha256) only, `user_id`, `revoked_at` |

Migrations: `c1d2e3f4a5b6` (Person KB) then `d2e3f4a5b6c7` (`mnp_web_sessions`).
Additive; PostgreSQL-compatible. Nothing in the existing person-side
schema is touched.

## 5. Mandatory / optional

* **Mandatory to create:** `first_name` only.
* **Mandatory to ACTIVATE (V1 rule):** name + at least one substantive
  fact block (education / experience / activity / skill / language). A
  partial DRAFT never auto-activates.
* Everything else may be UNKNOWN / blank.

## 6. Evidence model

`PersonEvidenceState` (one column per fact row):

| state | meaning |
|---|---|
| `self_reported` | person / admin entered it |
| `document_supported` | a supporting document is attached |
| `system_detected` | parser found a candidate — **NOT a confirmed fact** |
| `user_confirmed` | the person explicitly confirmed a CV candidate |

`source` (`PersonSource`) records the channel: `user_manual`,
`admin_manual`, `admin_edit`, `cv_import`, `cv_confirmed`. An admin edit
sets `source = admin_edit` and does **not** silently claim
`document_supported`.

No separate polymorphic evidence table — the per-row state + optional
`supporting_document_id` is the minimal safe model.

**Which evidence system does new code use?** `PersonEvidenceState` on the
canonical `MnpPerson` fact rows **is** the Base V1 canonical Person fact
verification state — `SELF_REPORTED` / `DOCUMENT_SUPPORTED` /
`SYSTEM_DETECTED` / `USER_CONFIRMED`. The old `MnpEvidence` /
`MnpCareerCard` evidence tables remain **only** for Matching
compatibility (they feed `app/services/matching_mnp`); they are **not**
the canonical Person KB evidence model and **new Person-side development
must not write to them**. No ambiguity: new code → `MnpPerson` +
`PersonEvidenceState`.

## 7. UNKNOWN != NO

Every yes/no fact is a tri-state string: `has_driver_license`, `has_car`,
`willing_to_relocate`, `is_current` → `yes` | `no` | `unknown`. There are
**no bare Booleans** on Person KB fact rows. `unknown` is first-class and
never rendered / treated as `no`. Regression:
`test_person_kb_base_v1.py::test_tristate_unknown_is_not_no`.

## 8. Skills taxonomy

`mnp_person_skills_v1.canonical_skill_id` → `mnp_skills.id` — the **same**
rows a `CareerSkillRequirement` points at. There is no
`person_skills_dictionary`. A skill the person typed that is not a
taxonomy term is stored as `raw_input` with `custom_status =
pending_review` — it never silently becomes a canonical skill and never
creates one. (Resolution reuses the Career KB `normalize_phrase` +
alias match — no fuzzy / LLM matching.)

Proficiency is nullable — **UNKNOWN proficiency ≠ beginner**. Never
fabricated.

## 9. CV flow

```
upload → extract_text → split_into_sections → parse_resume_sections (deterministic, no AI)
       → CANDIDATE facts (dict, held by the browser, NOT persisted)
       → user review screen: confirm / edit / reject / add
       → apply_confirmed → Person KB rows (evidence_state = user_confirmed, source = cv_confirmed)
```

* The uploaded file is **always** saved as an `MnpPersonDocument` (type
  CV) — even on a parse failure, nothing is lost.
* Parse failure → `{"parsed": false, "fallback": "…заповнити профіль
  вручну"}` — the manual flow stays available, no stack trace.
* Extraction is only what a CV plausibly contains — name, contact,
  location, education, credentials, employment (raw titles, companies,
  dates, responsibilities), explicit skills, languages. **No** inference
  of personality / motivation / work values / leadership level / career
  potential.
* Reuses `app/services/resume_parser_mnp` pure functions (no AI, no LLM
  tokens). Parser accuracy for free-form Ukrainian CVs is imperfect — the
  review screen is the correction point (see §13 Known Limitations).

## 10. Manual user flow

`#/profile` → **Завантажити резюме** or **Заповнити самостійно**.

Manual (`#/profile/build`): 8 steps — Про мене · Освіта · Досвід (with an
explicit "у мене ще немає досвіду" path — just skip) · Проєкти та
активності · Навички та інструменти (canonical search + "Додати своє") ·
Мови · Мобільність · Перевірка → Save.

`#/profile/edit` — reopen, tabbed edit, save/reload. A user can only ever
touch their own profile (resolved from the authenticated identity, never
a path id).

## 11. Admin flow

`#/admin/persons` — list (Ім'я / Телефон / Email / Telegram / Місто /
Статус / Оновлено) + search + `+ Створити профіль`.

`#/admin/persons/{id}` — 9 tabs (Основне · Освіта · Досвід · Проєкти та
активності · Навички та інструменти · Мови · Сертифікати / Кваліфікації ·
Документи · Мобільність). Every BASE field editable; add / edit / delete
nested rows; activate / archive / unarchive. Reload shows identical
values.

## 12. Excel

```
MNP_DATABASE_URL=sqlite+aiosqlite:///./data/dev/mnp_dev.sqlite \
    python -m data_explorer.cli export-persons-excel
```

→ `data/data_explorer/exports/MNP_PERSON_KB_V1.xlsx` (gitignored). 11
sheets: `00_README, 10_PERSONS, 20_EDUCATION, 30_CREDENTIALS,
40_EXPERIENCE, 50_ACTIVITIES, 60_SKILLS_TOOLS, 70_LANGUAGES, 80_MOBILITY,
85_DOCUMENTS, 90_EVIDENCE`. Ukrainian-first headers + human labels;
English codes + IDs alongside for traceability. **DB → Excel only** — no
reverse path. Test: `test_person_kb_export.py` +
`test_excel_reflects_db_after_edit`.

## 13. Privacy & authentication

* **`POST /v1/mnp/session`** mints `{user_id, session_token}` — a 256-bit
  `secrets.token_urlsafe(32)` bearer token. Only `sha256(token)` is
  stored (`mnp_web_sessions.token_hash`); the raw token is returned once
  and never logged. The token is **not derivable from `user_id`**.
* **Person KB user routes** authenticate with `Authorization: Bearer
  <session-token>` **only** (`get_mnp_session_user`). A client-supplied
  `X-Mnp-User-Id` is **never trusted** on Person routes — a user cannot
  select an arbitrary identity by learning another UUID. The identity is
  resolved server-side from the session.
* The legacy non-Person MNP endpoints (`/career-card`, `/questionnaire/*`,
  `/match-runs`) now also honour the bearer token, keeping the historical
  `X-Mnp-User-Id` only as a backward-compat fallback (documented lower
  assurance; not used for PII).
* Admin routes → admin bearer (`get_current_admin`), unchanged. A Person
  session token does **not** unlock admin routes.
* Person KB is never on a public/anonymous route.
* PII (phone / email / telegram / CV text / document contents / DOB /
  full payload) is not written to logs; `AuditLog` for a Person records
  the action + field names, not values.
* Tests use synthetic personas only.

## 14. Old person-side architecture — disposition

| component | disposition | why |
|---|---|---|
| `MnpSkill` / `MnpSkillAlias` / `MnpUnmappedPhrase` | **REUSED** | canonical skill taxonomy, shared with Career KB (§8) |
| `app/services/resume_parser_mnp` (pure extraction) | **REUSED** | CV text/section/entity extraction (§9) |
| `settings.mnp_resume_storage_dir` | **REUSED** | Person document storage |
| Identity / `IdentityUser` / auth | **KEEP_INFRASTRUCTURE** | user identity, reused as-is |
| `MnpCareerCard` + children (`MnpExperience`, `MnpEducation`, `MnpCredential`, `MnpLanguage`, `MnpAchievement`, `MnpPersonSkill`, `MnpPersonKnowledge`, `MnpEvidence`, `MnpCareerCardVersion`) | **KEEP_INFRASTRUCTURE (superseded for new dev)** | still consumed by `app/services/matching_mnp` + the questionnaire flow + their tests. Not deleted — a Person KB → Matching adapter is a future step. **New development targets `MnpPerson`.** |
| `MnpCareerGoal` / `MnpIncomeTarget` / `MnpPreferenceProfile` / `MnpWorkValue` / `MnpPersonWorkValue` / `MnpConstraint` / `MnpLearningCapacity` | **KEEP (out of Person KB Base V1 scope)** | preference/values layer — a later workstream, not fact-first |
| DELETED | **none** | matching still needs the old stack; nothing is provably unused yet |

`PersonEvidenceState` on `MnpPerson` fact rows is the **canonical Person KB evidence model** for new development. `MnpEvidence` / `MnpCareerCard` evidence is retained for Matching only — new Person code never writes to it.

**Canonical Person Source of Truth going forward: `MnpPerson`.** No
ambiguity — the old `MnpCareerCard` is a matching-compat artifact.

## 15. Person → Resume / Person → Matching

* **Resume** — a future Resume Builder reads `MnpPerson` facts. Not built
  in V1.
* **Matching** — Matching compares Person KB ↔ Career KB. V1 does **not**
  wire `MnpPerson` into `run_match` (which still keys off
  `MnpCareerCard`). A `MnpPerson → matching input` adapter is the next
  Person-domain step. Existing matching is untouched.

## 16. Future extensions

Person KB → Matching adapter · Person KB → Resume Builder · preference /
values layer (from the retained tables) · document OCR · skill
verification workflow · taxonomy review UI for `pending_review` skills.

## 17. Customer Product UI V1 (NAPRIAM Phase 1)

The customer-facing frontend was reworked from the plain V1 technical UI
into the **NAPRIAM** product shell (branch `person-kb-base-v1`, PR #25).
**No backend architecture changed** — the same Person KB DB / API / bearer
sessions and the same Career KB power it.

Full screen map + state (FUNCTIONAL / VISUAL-FUTURE / NOT IMPLEMENTED),
the post-profile workspace shell, and the Career KB public/admin/internal
scope rule: **`docs/product/NAPRIAM_PRODUCT_UI_V1.md`**.

### Implemented (functional, end-to-end)

| area | route | notes |
|---|---|---|
| Public shell + header | all `#/…` (hidden on `#/admin`) | brand + nav (Як це працює · Професії · Можливості · Про нас); auth-aware right side |
| Home | `#/` | hero, CV drop-zone, «Заповнити вручну», illustrative result preview clearly marked «Приклад результату» |
| How it works | `#/how` | 4 conceptual steps, no metrics |
| About | `#/about` | mission only, no fabricated counts |
| Create profile | `#/profile` | two functional methods + disabled LinkedIn card («Незабаром») |
| Manual profile | `#/profile/build` | 8-step stepper (unchanged flow) → confirmation |
| CV upload / parse / review | `#/profile/cv` | drop-zone, grouped candidate preview, reject/confirm → confirmation; parser failure keeps the file + offers manual |
| Profile confirmation | `#/profile/confirmed` | «Ми проаналізували ваш досвід» — friendly evidence labels |
| My Profile | `#/profile/me` | read-only human-readable `MnpPerson`; actions: Редагувати · Оновити з CV · Переглянути професії; survives reload |
| Edit profile | `#/profile/edit` | tabbed editor (unchanged) |
| Career catalog | `#/catalog` | real Career KB (150 / 5 ACTIVE / 145 DRAFT), NAPRIAM cards, no personalized %, no salary |
| Career detail | `#/catalog/{id}` | real Career KB sections; market section → «Дані ринку будуть додані пізніше» |
| Opportunities | `#/opportunities` | honest future state — «Персональний підбір … на наступному етапі», routes to the catalog |
| Login (visual) | `#/login` | Email/Password/Google/LinkedIn shown **disabled** with «Незабаром» |
| Admin | `#/admin/…` | unchanged, plain internal UI, no customer header, not linked from customer nav |

### Deferred to later phases (shown only as disabled «Незабаром» or honest empty state)

Production authentication (email/password) · Google OAuth · LinkedIn
OAuth / LinkedIn import · personalized Matching + `MnpPerson → matching`
adapter · personalized career recommendations / match % · Market KB ·
salary / demand / employer intelligence · transition Route Builder ·
skill-gap engine · What-if simulator · Resources section · consultations.

### Control convention

Every customer control is either **FUNCTIONAL** (works end-to-end) or
**FUTURE** (visible, disabled, `«Незабаром»`, no navigation, no fake
action). No fabricated user results, no fabricated market data anywhere.

## 18. Operations (Founder — test without a developer)

```bash
# 1. build schema + seed (Career KB 150 + 2 demo persons)
python -m scripts.dev_seed --serve                 # or --reset --serve to rebuild

# server:  http://127.0.0.1:8099
# user:    http://127.0.0.1:8099/mnp/#/profile
# admin:   http://127.0.0.1:8099/mnp/#/admin/login   (admin@mnp.local / mnp-dev-admin)
#            then  #/admin/persons

# Excel:
MNP_DATABASE_URL="sqlite+aiosqlite:///./data/dev/mnp_dev.sqlite" \
    python -m data_explorer.cli export-persons-excel
#   -> data/data_explorer/exports/MNP_PERSON_KB_V1.xlsx

# migration (Postgres):
python -m alembic upgrade head        # head = c1d2e3f4a5b6

# focused tests:
pytest tests/test_person_kb_base_v1.py tests/data_explorer/test_person_kb_export.py -q
```
