# METHODOLOGY_FINDING — 5 approved P0 documents are missing from the repository

**Type:** documentation gap (not a methodology error).
**Raised by:** MNP DATA EXPLORER V1, BLOCK 1.
**Date:** 2026-08-30.
**Needs:** Founder decision on where the canonical text lives.

---

## Evidence

`docs/mnp_v1/00_DOCUMENT_INDEX.md` lists 44 documents. The working tree
(on every branch that has `docs/mnp_v1/` — `mnp-v1-implementation`,
`product-system-v3.1`) contains **39 Markdown files + a ZIP + an install
note**. The following, all referenced by the DATA EXPLORER brief §2 as
source of truth, **do not exist as files**:

| Missing file | Referenced by |
|---|---|
| `01_FOUNDATION/MNP_METHODOLOGY_V1.md` | brief §2; `00_README.md` source-of-truth order |
| `02_DOMAIN/MNP_DATA_MODEL_V1.md` | brief §2; docstrings in `app/db/models_career_kb_mnp.py`, `models_matching_mnp.py` |
| `02_DOMAIN/MNP_SKILL_SCHEMA_V1.md` | brief §2; docstrings in `app/db/models_career_card.py` |
| `02_DOMAIN/MNP_CAREER_PROFILE_SCHEMA_V1.md` | brief §2; docstrings in `models_career_kb_mnp.py` (§3, §4, §5, §22, …) |
| `02_DOMAIN/MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1.md` | brief §2, §15 |

The whole `02_DOMAIN/` folder is absent. `MNP_DEVELOPMENT_PACKAGE_V1.zip`
is **7 500 bytes on every branch** and does not open as a valid archive —
it cannot be the 44-document bundle `PACKAGE_INSTALL.md` describes.

## Observed problem

The DATA EXPLORER must not invent a schema, but its human-lab entities
(Person Profile, Career Comparison, Expected Result — brief §15–§19) have
to line up with the approved MNP domain model, and its external-mapping
review artifacts (brief §10–§11) have to line up with the approved
`MnpExternalMapping` shape.

## Options

1. **Use the implemented code as the effective schema.** BLOCK A of
   `mnp-v1-implementation` implemented `MNP_DATA_MODEL_V1` /
   `MNP_SKILL_SCHEMA_V1` / `MNP_CAREER_PROFILE_SCHEMA_V1` /
   `MNP_EVIDENCE_AND_CONFIDENCE_MODEL_V1` as SQLAlchemy models
   (`app/db/models_career_kb_mnp.py`, `models_career_card.py`,
   `models_matching_mnp.py`) — the enums and field sets are concrete and
   internally consistent. The DATA EXPLORER aligns to that code.
2. Wait for the Founder to commit the 5 Markdown files, then reconcile.
3. Reconstruct the docs from the code + this branch's older
   `methodology_lab/` set (`MNP_HUMAN_POTENTIAL_MODEL_V0.1.md`,
   `MNP_CAREER_FIT_MODEL_V0.1.md`, `MNP_EVIDENCE_STANDARD_V0.1.md`).

## Recommendation

**Option 1 for now.** The DATA EXPLORER reads the concrete model classes
and mirrors their enums verbatim (`ProficiencyLevel`, `EvidenceType`,
`ExternalMappingType`, `FeasibilityStatus`, `TransitionDistance`,
`GapType`, `GapClassification`, `GapAction`, …). No methodology is
invented; if the Founder later commits the 5 docs and they differ from the
code, that is a separate reconciliation the Founder owns — the DATA
EXPLORER changes are additive and reversible.

Also recommend: **re-commit `MNP_DEVELOPMENT_PACKAGE_V1.zip`** (the
current blob is corrupt) so `PACKAGE_INSTALL.md`'s fallback works.
