# METHODOLOGY_FINDING — Career KB entity coverage vs the Career Dataset spec

**Type:** model-coverage gap (not a defect).
**Raised by:** MNP DATA EXPLORER V1 — Career Dataset / Career KB Export addendum.
**Date:** 2026-08-30.
**Needs:** Founder decision on whether to add the missing entities to the
production model (a separate methodology + `mnp-v1-implementation` task).

The DATA EXPLORER **did not create any production table** (brief §2 —
"Не создавай дублирующие таблицы"). Where the Career Dataset spec asks for
a field the approved MNP model has no place for, the exporter emits the
column with a blank cell / `UNKNOWN` and this finding records it.

---

## What the addendum asks for vs what the model has

| Addendum sheet | Approved MNP entity | Coverage |
|---|---|---|
| 10_CAREERS | `MnpCareer` + `MnpCareerFamily` | full — except **`difficulty_level`** has no dedicated field (exporter shows `catalog_priority`) |
| 20_SKILLS | `MnpCareerSkillRequirement` + `MnpSkill` (+ `MnpExternalMapping` entity_type=skill for `skill_code`) | full |
| 30_REQUIREMENTS | `MnpCareerRequirement` | full — `RequirementCategory` is `education\|experience\|credential\|language\|legal\|other`; the addendum's `certification` + `license` both map to `credential` |
| 40_RESPONSIBILITIES | `MnpCareerTask` (MNP_CAREER_PROFILE_SCHEMA_V1 §7) | full |
| 50_CAREER_PATHS | `MnpCareerRelation` | **partial** — the model stores career↔career *relations* (`progression\|adjacent\|related\|same_family\|common_transition`), **not** an ordered step sequence with `step_name` / `typical_experience` / `description`. A dedicated `MnpCareerPathStep` entity does not exist. |
| 60_PROS_CONS | *(none)* | **missing** — no `MnpCareerProsCons` entity. Empty sheet by design. |
| 70_MARKET_DATA | `MnpMarketSnapshot` + `MnpSalarySnapshot` | **partial** — has country/region/vacancy_count/demand_trend/remote_share + salary p25/median/p75. **No** `city`; **no** `salary_min` / `salary_max` (percentiles only); **no** `demand_level` (only `demand_trend` up/flat/down); **no** `currency` on the market snapshot (it is on the salary snapshot). *The alpha KB has zero market snapshots — every metric is blank, `MARKET_DATA_LIMITED`.* |
| 80_EXTERNAL_REFS | `MnpExternalMapping` (entity_type=career) | **partial** — has source_system / external_id / external_label / mapping_type / confidence / source_version. **No** `mapping_status`, `reviewed_by`, `reviewed_at` (the crosswalk-review lifecycle from `MNP_CAREER_KB_V1.md` §J is not in the SQLAlchemy model). Exporter shows `mapping_status='candidate'`, `reviewed_by/at` blank. |
| 90_PROVENANCE | *(derived)* | full — provenance is **not** a separate table by design; every KB row carries its own `source` / `source_version` / `confidence`. The exporter flattens them per field. This matches the model and brief §2 ("не хранить ... как один blob"). |

---

## Options

1. **Accept as-is for V1.** The gaps only matter when the KB grows past
   the 5-career alpha (career paths, pros/cons, real market data). The
   exporter already has the columns ready.
2. **Add the missing entities to the production model** — `MnpCareerPathStep`,
   `MnpCareerProsCons`, richer `MnpMarketSnapshot` (city, currency,
   demand_level), review-lifecycle fields on `MnpExternalMapping`. This is
   a methodology + `mnp-v1-implementation` migration task, **not** a DATA
   EXPLORER task.
3. **Hybrid** — represent pros/cons and career-path steps as
   `MnpCareerAttribute` rows (`attribute_group='pros_cons'` /
   `'career_path'`) so no new table is needed; the exporter would then
   populate those sheets from attributes.

## Recommendation

**Option 1 now, Option 2/3 when the catalogue expands to 50.** Nothing in
the current 5-career KB needs these entities. When the Founder greenlights
the 50-career build, decide 2 vs 3 then — the exporter and its tests are
already shaped for whichever way it goes.
