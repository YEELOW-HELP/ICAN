# Stage 3A: Curated Career Knowledge Base — Implementation Reference

Branch: `stage-3a-career-knowledge-base-v1` (based on `product-system-v3.1`
@ merged PR [#18](https://github.com/YellowHub-Ukraine/ICAN/pull/18), Stage 2).
Implements Issue #4: a trustworthy, versioned, source-backed knowledge
layer so Stage 3B's future Direction Intelligence never depends on
unverified LLM memory. **Does not build Direction Intelligence, ranking,
fit scores, Route Builder, or any Stage 3B arrow** — see §11 below for
the explicit boundary.

This document is a reference for engineers and reviewers — see
`docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md` §12 and
`15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md`'s "Sub-stage 6" for product
scope, and `docs/architecture/02_ERD.md` for the target `CAREER`/
`CAREER_SKILL`/`CAREER_EDGE`/`MARKET_SIGNAL` entities this narrows.

## 1. Why this schema isn't a copy of the target ERD

`02_ERD.md` sketches `CAREER`/`CAREER_SKILL`/`CAREER_EDGE`/
`MARKET_SIGNAL` only as relationship lines in its mermaid diagram — none
of them have a field-level shape specified anywhere in that document
(unlike `USER`/`CONSENT`/etc., which do). Per brief §6 ("design the
minimal production-grade V1 schema... do not blindly copy the target
ERD"), this is the first real schema design for these entities. Entity
*names* are kept where they map (`Career`, `CareerSkill`); new,
justified entities were added where provenance/versioning required them
(`KnowledgeBaseVersion`, `KnowledgeSource`, `CareerFact`,
`CareerRequirement`, `CareerWorkContext`, `CareerRelation`, `CareerAlias`).

## 2. Reuse decision: skills are Taxonomy content, not a new Skill table

`docs/engineering/13_FOUNDER_ARCHITECTURE_REVIEW.md` already names
"career taxonomy" as one of the categories the versioned `TAXONOMY`/
`TAXONOMY_VERSION`/`TAXONOMY_TERM` architecture (Stage 2,
`app/db/models_profile.py`) is meant to cover. Per brief §8, skills are
seeded as `TaxonomyTerm` rows under a new `Taxonomy(key="skills")`
(`app/services/knowledge/skills.py::ensure_skills_taxonomy`) —
`CareerSkill.skill_term_id` is a direct FK to `taxonomy_terms.id`. **No
new Skill table exists.** This also means skills get their taxonomy's
own independent versioning (`TaxonomyVersion.status`) for free, decoupled
from the Career Knowledge Base's own `KnowledgeBaseVersion` lifecycle.

## 3. New tables (`app/db/models_knowledge.py`)

| Table | Purpose |
|---|---|
| `knowledge_base_versions` | The publish-unit for the whole KB (§5). |
| `knowledge_sources` | Source provenance references (§7). |
| `careers` | One career/direction record per KB version (§4). |
| `career_aliases` | Ukrainian-first names/synonyms, locale-ready (§8). |
| `career_skills` | Links a career to a skill `TaxonomyTerm` (§2). |
| `career_requirements` | Entry barriers, certainty-graded (§6). |
| `career_work_contexts` | 1:1 environment/logistics attributes (§4). |
| `career_relations` | Trustworthy, queryable career-to-career edges (§9). |
| `career_facts` | Structured, source-referenced factual assertions (§7). |

Migration: `7d3720363f8e` (revises `0c9abc704162`, Stage 2's head),
additive, FK-ordered, downgrade reverses exactly. No existing table is
altered. `career_skills.skill_term_id` is the only FK reaching outside
this migration's own new tables (into Stage 2's `taxonomy_terms`).

**Bounded-domain separation** (brief §21, tested in
`tests/test_knowledge_retrieval.py::test_knowledge_models_have_no_foreign_key_into_user_or_assessment_tables`):
zero tables here have a foreign key into `identity_users`,
`interview_sessions`, `evidence`, or `profile_claims`. Career Knowledge
and User Evidence/Profile are separate bounded domains; no raw user
answer or CV content belongs in this schema, and none exists in it.

## 4. Career record

`Career`: `id`, `knowledge_base_version_id`, `code` (stable internal key,
unique *within* a version — see §5), `title_uk`/`title_en`, `domain`
(`CareerDomain` enum — the 16 structural categories from brief §15, same
"architectural not methodology" rationale as Stage 2's
`ProfileDimension`), `status` (`active`/`deprecated`/`draft`),
`short_description`, `typical_activities`, seven continuous 0.0–1.0
intrinsic-task characteristics (`works_with_people`, `works_with_data`,
`works_with_technology`, `creative_component`, `analytical_component`,
`autonomy_level`, `structure_routine_level` — all nullable: an uncurated
characteristic is absent, never defaulted to a fabricated midpoint), and
three external-taxonomy reference columns (§10).

**Never a fit score.** These characteristics describe the *work*, not
any candidate's suitability for it — user fit is entirely Stage 3B's
concern (brief §7's non-negotiable).

**Approved V1 trade-off (Founder-approved, explicitly not to be
"fixed" into JSON or a generic EAV model without a separate decision):**
the seven characteristics are explicit, typed, relational columns on
`Career`, not a `characteristics: JSON` blob and not a generic
entity-attribute-value table. This is a deliberate choice, weighed and
kept as-is in the Stage 3A review:

- **Queryable** — `find_careers(min_characteristics=..., max_characteristics=...)`
  (§11) compiles to plain indexed-comparable `WHERE` clauses; a JSON/EAV
  design would need JSON-path queries or a join-heavy value table for the
  same filters.
- **Typed** — each column is a real `Float`, so a malformed value (a
  string where a number belongs) is a schema violation, not a silent
  runtime surprise discovered deep in Stage 3B's matching logic.
- **Auditable** — the column list itself documents exactly which
  characteristics Stage 3A claims to model; nothing hides in an
  untyped bag that could silently grow inconsistent keys across careers.
- **The cost, accepted deliberately:** adding an eighth characteristic
  (or changing what one means) requires a migration, not a data-only
  change. Given `docs/architecture/02_ERD.md`'s database rule 1
  ("critical business data must be relational; JSON is for flexible
  snapshots, not the only source of truth"), this cost is the intended
  trade-off, not a gap to close.
- **Future methodology expansion** (a genuinely larger or restructured
  set of matching dimensions, e.g. driven by real Stage 3B/methodology
  research) may require an explicit schema evolution — a new migration
  adding columns, not a reinterpretation of the existing ones and not a
  quiet pivot to JSON to dodge the migration. That evolution, if and when
  it's needed, is a Stage 3B-or-later decision, not something this
  document pre-authorizes.

`CareerWorkContext` (one row per career) holds the environment/logistics
attributes (brief §10) split out for readability: `setting`
(office/remote/field/mixed), `indoor_outdoor`, `travel_required`,
`shift_work`, `physical_intensity`, `teamwork_level`,
`customer_interaction_level`, `client_facing`, `repetitive_vs_varied`,
`schedule_predictability`, `responsibility_level`, `stress_level`. Split
from `Career`'s own characteristics purely for readability — both are
"structured attributes usable without parsing prose," grouped by what
they describe (the work's intrinsic nature vs. the setting it happens
in), with no field duplicated across the two.

## 5. Knowledge Base versioning (brief §14)

`KnowledgeBaseVersion` is a **single global version counter** for the
whole Career Knowledge Base — the same "one incrementing version, one
`is_current` flag, old versions never edited" idiom Stage 2 already
established for `PotentialProfile`. Lifecycle: `DRAFT` → `PUBLISHED` →
`SUPERSEDED`, enforced by `app/services/knowledge/versioning.py`:

- `create_draft_version()` — `version = max(existing) + 1`.
- `publish_version(draft_id)` — flips the version to `PUBLISHED`,
  `is_current=true`; if a previous version was `is_current`, it is
  atomically flipped to `SUPERSEDED`/`is_current=false` in the same
  transaction. A partial unique index
  (`uq_one_current_knowledge_base_version`, `WHERE is_current = true`)
  makes "at most one current version" a DB-enforced invariant, not a
  convention.
- Careers/skills/requirements/relations may only be added to a `DRAFT`
  version (`get_draft_version` raises `KnowledgeBaseVersionNotDraftError`
  otherwise) — a `PUBLISHED` version is immutable.

**`Career.code` is unique per version, not globally**
(`UNIQUE(knowledge_base_version_id, code)`): republishing the KB with an
updated "software_developer" record creates a *new* `Career` row tagged
with the new version — never an edit to the old one. This is what makes
"an old report must still be able to identify which knowledge version
was used" (brief §14) concretely true: a consumer that stored
`knowledge_base_version_id` alongside a generated artifact can always
re-resolve exactly the `Career` rows that existed at that time, even
after the KB has moved on.

## 6. Entry barriers / requirements (brief §9)

`CareerRequirement.certainty` is the load-bearing field:

- `HARD_FACTUAL` — a verified, sourced fact. **Requires `source_id`**,
  enforced in `app/services/knowledge/careers.py::add_career_requirement`
  (`HardFactualRequirementRequiresSourceError` otherwise) — service-layer
  enforcement, not a DB `CHECK` constraint, consistent with this
  codebase's existing convention (RBAC, idempotency, etc. are all
  enforced the same way).
- `TYPICAL_RECOMMENDATION` — a curated, reasonable general expectation
  (e.g. "a nursing degree is typically expected"), not asserted as a
  verified legal fact. No source required.
- `UNKNOWN` — explicitly not curated. No source required.

The Stage 3A seed uses `TYPICAL_RECOMMENDATION` exclusively (see §9) —
it cites no actual jurisdiction-specific legal source, so it never
claims `HARD_FACTUAL`.

**Stage 3B contract (Founder-approved, binding on the future Direction
Intelligence engine):** `CareerRequirement.certainty ==
TYPICAL_RECOMMENDATION` **MUST NOT** be treated as an automatic hard
blocking constraint by any future matching/ranking logic. It is a
curated, generally-reasonable expectation an editor wrote down — not a
verified, jurisdiction-specific legal fact — and Stage 3A never claims
otherwise. A future hard block (e.g. "this candidate's hard constraint
makes career X impossible") may rely **only** on requirement data that
is sufficiently authoritative and machine-readable per whatever Stage
3B/methodology contract eventually defines that bar — which, for a
`CareerRequirement`, effectively means `certainty == HARD_FACTUAL` (and
therefore carries a real `source_id`), not `TYPICAL_RECOMMENDATION` or
`UNKNOWN`. Every `CareerRequirement` in the Stage 3A seed is
`TYPICAL_RECOMMENDATION` (§9) precisely so that a naive future
implementation that *did* wire "any requirement" into a hard blocker
would immediately and visibly over-block on seed data that was never
meant to carry that weight — this is a deliberate safeguard, not an
oversight to fix later. Stage 3A implements no matching logic at all;
this paragraph exists solely so Stage 3B cannot accidentally
misinterpret what `certainty` already on disk actually means.

## 7. Source provenance (brief §12) and market-sensitive facts (brief §20)

`KnowledgeSource`: a reference (`publisher`, `title`, `url`,
`country_region`, `publication_date`, `accessed_at`/`verified_at`,
`trust_level`, `status`) — never a copy of the source document itself.

`CareerFact.is_market_sensitive=true` (salary, demand, growth, vacancy
counts, employment outlook, ...) **requires both `source_id` and
`as_of_date`**, enforced in
`app/services/knowledge/careers.py::add_career_fact`
(`MarketSensitiveFactRequiresSourceError` otherwise). A
non-market-sensitive fact (e.g. "remote work is sometimes possible" as a
structural observation) does not require a source — mirroring the same
"curated classification vs. sourced market claim" distinction §9 draws
for requirements.

**The Stage 3A seed contains zero `CareerFact` rows** — no salary,
demand, or any other market-sensitive data was fabricated to fill the
mechanism out; the mechanism is proven by direct unit tests
(`tests/test_knowledge_careers.py`) instead of by populating it with
invented seed data. "Unknown" beats a plausible-looking fabrication.

`get_sources_for_career()` (`app/services/knowledge/retrieval.py`)
answers "where did this come from?" for a whole career at once — the
union of every `KnowledgeSource` referenced by any of its skills,
requirements, relations, or facts.

## 8. Career skills and relations

`CareerSkill.source_id` is **optional** — a curated skill-relevance
judgment (required/preferred/useful) is methodology content, the same
kind Stage 2 seeded into `TaxonomyTerm` without a per-term citation, not
necessarily a single citable market fact.

`CareerRelation` (`adjacent_to`/`progression_to`/`specialization_of`/
`related_to`/`transition_possible_to`) connects two `Career` rows.
**Both ends must belong to the same `KnowledgeBaseVersion`** — enforced
in `add_career_relation` (`CrossVersionRelationError` otherwise), since a
relation spanning two different KB snapshots is never a meaningful thing
to create. `UNIQUE(from_career_id, to_career_id, relation_type)` prevents
duplicate edges. No pathfinding/Route Builder exists — this is
deliberately just the relationship facts a future Route Builder could
use (brief §11).

## 9. Curated seed (brief §15/§26)

32 careers — exactly 2 per `CareerDomain`, covering all 16 domains —
chosen for structural diversity so a future Stage 3B ranking test can
detect an obviously wrong recommendation. Full list in
`app/services/knowledge/seed.py::_CAREERS`:

| Domain | Careers |
|---|---|
| technology | software_developer, it_support_specialist |
| healthcare | registered_nurse, pharmacist |
| engineering | civil_engineer, mechanical_engineer |
| logistics_transport | truck_driver, logistics_coordinator |
| skilled_trades | electrician, plumber |
| sales | sales_manager, retail_sales_associate |
| customer_service | customer_service_representative, call_center_operator |
| management | operations_manager, project_manager |
| finance | accountant, financial_analyst |
| education | school_teacher, corporate_trainer |
| creative | graphic_designer, video_editor |
| marketing | marketing_specialist, social_media_manager |
| social_sector | social_worker, community_outreach_coordinator |
| administration | administrative_assistant, office_manager |
| hospitality_service | hotel_receptionist, chef_cook |
| manufacturing | production_line_operator, quality_control_inspector |

Every career has: a Ukrainian canonical title + at least one alias, a
short description and typical activities, all seven intrinsic-task
characteristics, a full `CareerWorkContext` row, 2–4 linked skills (from
the shared `skills` taxonomy, ~36 terms), and zero-to-two
`CareerRequirement` rows. 12 `CareerRelation` edges connect related/
progression-adjacent careers (e.g. `retail_sales_associate ->
sales_manager` progression, `electrician <-> plumber` adjacency).

**Sourced vs. omitted, explicitly:**
- Structural/classification fields (description, activities,
  characteristics, work context, skill relevance) — curated judgment,
  same standing as Stage 2's seeded taxonomy terms. Populated.
- `CareerRequirement` rows — all `certainty=TYPICAL_RECOMMENDATION`, no
  `source_id`. Never `HARD_FACTUAL` (no jurisdiction-specific legal
  source was actually cited).
- `CareerFact` rows — **none**. No salary/demand/growth/vacancy data
  anywhere in the seed.

`ensure_seed_knowledge_base()` is idempotent: if any
`KnowledgeBaseVersion` already exists, it returns the current one
without creating a duplicate draft or re-inserting careers.

## 10. External taxonomy readiness (brief §16)

`Career.external_esco_id`/`external_onet_id`/`external_isco_id` are
nullable reference columns, unpopulated in the V1 seed. **These are
never primary business IDs** — `Career.id` (UUID) and `Career.code`
(stable internal key) remain canonical; an external ID is purely a
future cross-reference, safe to add or remove without touching how
anything internally identifies a career.

## 11. Retrieval service layer (brief §17) — the Stage 3B boundary

`app/services/knowledge/retrieval.py` is the **only** intended query
surface for a future Direction Intelligence service — no raw SQL should
ever be written against these tables outside this module:

`get_current_knowledge_version()`, `get_career(id)`,
`get_career_by_code(code, knowledge_base_version_id=None)`,
`find_careers(domain=, status=, min_characteristics=, max_characteristics=)`,
`get_career_details(id)` (bundles career + aliases + skills +
requirements + work context + relations + facts), `get_career_skills`,
`get_career_requirements`, `get_career_relations`, `get_career_facts`,
`get_sources_for_career`, `search_careers(query, locale="uk")`.

Every function defaults to the current published version unless an
explicit `knowledge_base_version_id` is given (`
test_retrieval_defaults_to_current_version_even_after_republish` proves
old-version lookups keep working after a republish). **No AI Gateway
call exists anywhere in this module** — retrieval is entirely
deterministic (brief §23).

**This module's read surface is the explicit, intentional boundary of
Stage 3A.** It does not rank, score, filter for a specific person's fit,
or combine with any `PotentialProfile`/`Evidence` data — that arrow
(`Human Potential Profile + Knowledge Base -> Direction Intelligence`) is
Stage 3B, not implemented here.

## 12. Ukrainian search / aliases (brief §18)

`CareerAlias.normalized_text` (lowercased + whitespace-collapsed via
`careers.py::normalize_alias_text`) is a real, indexed column — not
computed per-query — so `search_careers()` stays a plain equality/`LIKE`
match. `locale` is a first-class column on every alias; `search_careers`
already takes a `locale` parameter and switches which title column
(`title_uk`/`title_en`) it matches against. Adding `de`/`ru` aliases
later needs zero code changes here, only new `CareerAlias` rows.

## 13. Privacy / auditability / write-path contract

**Founder-approved architectural contract (Stage 3A review):** every
mutation of a Career Knowledge Base entity — `Career`, `CareerAlias`,
`CareerSkill`, `CareerRequirement`, `CareerWorkContext`, `CareerRelation`,
`CareerFact`, `KnowledgeSource`, `KnowledgeBaseVersion` — **MUST** go
through `app/services/knowledge/*` (`careers.py`, `versioning.py`,
`skills.py`). This is what makes the provenance guarantees in §6/§7 real:
`HardFactualRequirementRequiresSourceError` and
`MarketSensitiveFactRequiresSourceError` are raised by
`careers.add_career_requirement`/`add_career_fact` themselves — a caller
that constructs `CareerRequirement(certainty=HARD_FACTUAL, ...)` or
`CareerFact(is_market_sensitive=True, ...)` directly via the ORM and
calls `session.add()`/`session.commit()` bypasses those checks entirely,
since nothing at the database schema level (no `CHECK` constraint)
enforces them — this is a deliberate, documented V1 trade-off (see §6),
not an oversight, and it is exactly why the *service layer itself* is
the approved write path, not merely a convenience wrapper around it.

`tests/test_knowledge_careers.py::test_direct_orm_write_bypasses_provenance_guards_this_is_why_the_service_layer_is_the_contract`
demonstrates this concretely: a direct `session.add(CareerFact(...))`
with `is_market_sensitive=True` and no `source_id` **succeeds** at the
ORM/DB level, while the equivalent call through
`careers.add_career_fact()` raises. The test exists to make the
contract's necessity legible in the test suite itself, not just in prose.

**Concretely, this means:**
- **Approved write path:** any future handler, API endpoint, or Admin
  curation surface (Stage 3B+) calls
  `careers.create_career()`/`add_career_alias()`/`add_career_skill()`/
  `add_career_requirement()`/`set_career_work_context()`/
  `add_career_relation()`/`add_career_fact()`/`create_knowledge_source()`
  and `versioning.create_draft_version()`/`publish_version()` — never
  raw ORM inserts/updates against these tables from outside
  `app/services/knowledge/`.
- **Not approved:** direct `session.add(Career(...))` /
  `session.execute(update(CareerFact)...)` etc. from a route handler,
  admin controller, script, or any other future caller. There is
  nothing technically stopping this (no DB `CHECK`, no ORM-level guard),
  which is precisely why it is a documented *contract*, not a
  self-enforcing property of the schema.
- **A future Admin curation API (Stage 3B+) must preserve the same
  guards** by calling these same functions, not by reimplementing
  equivalent validation in the API/handler layer — do not duplicate the
  `HARD_FACTUAL`/market-sensitive business rules a second time elsewhere;
  the single source of truth for them stays
  `app/services/knowledge/careers.py`.
- Every mutation already goes through a service function in this
  codebase today (`create_career`, `add_career_*`, `publish_version`) —
  this section documents that as a binding contract for all future
  callers, not merely today's incidental structure.

Additional privacy notes:
- No table in this migration references user/assessment/profile data
  (§3). No raw user answer or CV text has ever touched this schema.
- Zero `logger.*` calls anywhere in `app/services/knowledge/`.
- No AuditLog integration was added: Stage 3A introduces no privileged
  *user-facing* admin action yet (no admin UI exists to gate) — the
  version-immutability model itself (§5) is what currently prevents
  silent overwrites. A future Admin curation API, per the contract above,
  should wire `record_audit()` into these same service functions rather
  than adding a parallel write path that would need its own auditing.

## 14. AI usage (brief §23)

**None at runtime.** No `app/services/knowledge/*` module imports
`AIGateway` or any provider SDK. All retrieval and seeding is
deterministic Python + SQL. If AI-assisted normalization is ever added
(e.g. to help curate a new career's characteristics from source text), it
must go through `AIGateway` like every other AI task in this codebase,
with structured-output validation, and its output must land as a `DRAFT`
`Career`/`CareerFact` — never auto-trusted into a `PUBLISHED` version.

## 15. Tests

| File | Covers |
|---|---|
| `test_knowledge_versioning.py` (8) | Draft/publish/supersede lifecycle, current-version invariant, historical preservation |
| `test_knowledge_careers.py` (17) | Code uniqueness per version, draft-only mutation, alias normalization, skill↔taxonomy linkage, HARD_FACTUAL/market-sensitive provenance enforcement, cross-version relation rejection, source traceability, and the write-path contract (§13: a direct ORM write bypasses the same guard the service layer enforces) |
| `test_knowledge_retrieval.py` (11) | Retrieval API, domain/characteristic filters, Ukrainian/English alias search, version-scoped lookups after republish, bounded-domain FK isolation |
| `test_knowledge_seed.py` (6) | Idempotency, no duplicates, diversity, aliases/skills/work-context completeness, no HARD_FACTUAL-without-source, zero market-sensitive facts, relation integrity |

Plus the existing `tests/test_migrations.py` (structural: single head,
fully linked chain, no duplicate revisions) and
`tests/test_migrations_postgres.py` (real PostgreSQL, CI-only) both pick
up the new migration automatically — no test-file changes needed there.

**Full regression: 333 passed, 2 skipped** (the two skips are the
Postgres-only migration test, expected locally). All Stage 1/Stage 2/
legacy tests remain green, untouched.

## 16. Known limitations / deferred tech debt

- No admin UI/API surfaces knowledge curation yet — every function in
  `app/services/knowledge/` is called directly (from the seed script and
  tests today; from a future admin surface or Stage 3B tooling later).
- No `AuditLog` integration (see §13) — added once a real privileged
  curation surface exists.
- The seven `Career` characteristics are a fixed, hand-designed set for
  V1 — extending or restructuring them requires a migration, by design;
  see §4's "Approved V1 trade-off" for the full rationale.
- External taxonomy IDs (ESCO/O*NET/ISCO) are schema-ready but
  unpopulated — no mapping work was done in Stage 3A.
- The skills taxonomy (~36 terms) and the 32-career seed are both
  intentionally minimal, representative content, not final methodology
  or an exhaustive corpus.

## 17. Acceptance criteria (Issue #4) — status

- Direction Intelligence can retrieve relevant curated knowledge — ✅,
  `app/services/knowledge/retrieval.py`'s full API, deterministic, no AI
  dependency.
- Market-sensitive claims have source/date or are omitted/qualified —
  ✅, enforced in `add_career_fact`; the seed itself omits all such
  claims entirely.
- Knowledge changes are versioned and auditable — ✅, `KnowledgeBaseVersion`
  lifecycle, immutable once published, `is_current` DB-enforced.
- Ukrainian aliases/search are supported — ✅, `CareerAlias` +
  `search_careers`, locale-ready for future languages.
