# MNP EXTERNAL MAPPING SPEC (DATA EXPLORER V1)

How the DATA EXPLORER proposes and records mappings between MNP entities
and external sources, so its review artifacts drop straight into the
production `MnpExternalMapping` table without any schema change.

## The one rule

`MNP_CAREER_ID` and `MNP_SKILL_ID` are the only identities. An ESCO URI,
an O*NET-SOC code, an ISCO code — these are **references stored beside**
an MNP entity, never a primary key, never a lookup key in engine logic,
never a de-dup key (Founder Decision #16).

```
MnpCareer.code  ─┐
                 ├─ MnpExternalMapping ─┬─ (esco)  ESCO occupation URI
MnpSkill.id  ────┘                      ├─ (onet)  O*NET-SOC code
                                        ├─ (isco)  ISCO-08 group code
                                        └─ (ua_classifier)  — not in Explorer V1 scope
```

## Fields (mirrors `app/db/models_career_kb_mnp.py::MnpExternalMapping`)

| field | values | notes |
|---|---|---|
| `entity_type` | `career` \| `skill` | |
| `mnp_entity_id` | `MnpCareer.id` \| `MnpSkill.id` | polymorphic pointer |
| `source_system` | `esco` \| `onet` \| `isco` \| `ua_classifier` | Lightcast is **not** a valid value |
| `external_id` | ESCO URI / O*NET-SOC / ISCO code | verbatim |
| `external_label` | preferred label at import time | |
| `mapping_type` | `exact` \| `close` \| `broad` \| `narrow` | see below |
| `confidence` | `0.0`–`1.0` \| `NULL` | `NULL` until a human reviews |
| `source_version` | e.g. `esco_v1.2.1`, `onet_31.0` | |

## DATA EXPLORER adds a review lifecycle on top

The Explorer never writes `MnpExternalMapping` directly. It produces a
**review sheet** (`55_CAREER_COMPARISON` / a `mapping_review` table) with
one extra column:

| `review_state` | meaning |
|---|---|
| `candidate` | suggested by the Explorer, not yet looked at |
| `confirmed` | a human confirmed it → eligible to become a `MnpExternalMapping` row |
| `review_required` | ambiguous / conflicting candidates → a human must choose |
| `rejected` | a human rejected it (kept for audit) |
| `unmapped` | a human looked and found no defensible mapping (a deliberate statement, not silence) |

Only `confirmed` rows are exported to production, and only by an explicit
Founder/editor action — **never auto-approved** (brief §27).

## How candidates are generated (no AI — brief §10, §27)

For a career, in priority order:

1. **Official ESCO↔O*NET crosswalk** (`xwalk_esco_onet`) — if the MNP
   career already has an ESCO *or* O*NET mapping, the crosswalk gives the
   other side for free. `mapping_type` is left **`unspecified`** (the
   O*NET-hosted flat file carries no relation semantics) — it is
   **never** promoted to `exact`.
2. **ISCO bridge** — MNP career → ISCO group (editorial or via ESCO) →
   all ESCO occupations / O*NET-SOC in that group, as `broad` candidates.
3. **Normalised English-title match** against `onet_occupation_title`
   (primary weighted far above alternate/reported) and
   `esco_occupation` + `esco_occupation_label`. Deterministic token +
   sequence similarity (the approach reused from commit `6d27bf3`).

Each candidate row records **which signal produced it** and a score.
A human reads the row and sets `review_state` + `confidence` + `mapping_type`.

## Non-exact is never exact

A crosswalk / ISCO-bridge / title-match candidate is at best `close` or
`broad`. `mapping_type = exact` may only be set by a human who has read
both concept definitions. The Explorer's data-quality check asserts
`count(mapping_relation = 'exact') == 0` in `xwalk_esco_onet`.

## Skills

Same model. Candidates come from: ESCO `occupationSkillRelations`
(essential/optional) for a mapped ESCO occupation; O*NET
essential/transferable skills + knowledge for a mapped O*NET-SOC; ESCO
skill-label match. An unknown external skill phrase **never**
auto-creates an `MnpSkill` (Founder Decision #21 / `MnpUnmappedPhrase`
precedent) — it lands as `review_required`.
