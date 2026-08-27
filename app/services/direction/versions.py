"""Version identifiers stamped on every Direction Intelligence artifact
(Founder decisions M + G + plan section 15: reproducibility).

Single source of truth for the strings written to `DirectionRun.*_version`
columns. Bump the specific constant when the corresponding methodology
document or engine behaviour changes -- never reuse a string across
incompatible behaviour.
"""

from __future__ import annotations

# methodology_lab/02_HUMAN_POTENTIAL_MODEL/MNP_HUMAN_POTENTIAL_MODEL_V0.1.md
METHODOLOGY_VERSION = "mnp-hpm:v0.1"

# methodology_lab/03_EVIDENCE_STANDARD/MNP_EVIDENCE_STANDARD_V0.1.md
EVIDENCE_STANDARD_VERSION = "mnp-evidence-standard:v0.1"

# methodology_lab/04_CAREER_FIT_MODEL/MNP_CAREER_FIT_MODEL_V0.1.md
# (the four-output Direction Evaluation Model: Potential Fit / Goal
# Alignment / Transition Feasibility / Evidence Confidence)
DIRECTION_EVALUATION_MODEL_VERSION = "mnp-direction-evaluation-model:v0.1"

# methodology_lab/04_CAREER_FIT_MODEL/MNP_RANKING_POLICY_V0.1.md
# Ranking is a SEPARATE versioned decision layer (Founder decisions A/G) --
# never part of the definition of Potential Fit.
RANKING_POLICY_VERSION = "mnp-ranking-policy:v0.1"

# app/services/direction/dimension_mapping.py -- legacy ProfileDimension -> canonical
DIMENSION_MAPPING_VERSION = "legacy-to-mnp:v0.1"

# app/services/direction/dimensions.py -- subdimension taxonomy content
SUBDIMENSION_TAXONOMY_VERSION = "mnp-hpm-subdimensions:v0.1"

# MNP-HPM section 3.3 -- the 12-subtype constraint taxonomy (Founder decision D).
CONSTRAINT_TAXONOMY_VERSION = "mnp-constraint-taxonomy:v0.1"

# This module's own engine behaviour. Slice suffix is intentional: Slice 1
# is deterministic foundation only -- no ranking orchestration, no
# narrative, no critic.
DIRECTION_ENGINE_VERSION = "direction-intelligence:v0.1-slice1"
