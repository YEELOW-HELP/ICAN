"""MNP V1 -- deterministic Matching Engine (`MNP_MATCHING_MATH_V1`,
`MNP_FEASIBILITY_RULES_V1`, `MNP_TRANSITION_DISTANCE_V1`,
`MNP_SKILL_GAP_AND_PRIORITY_V1`, `MNP_RANKING_MODES_V1`). No LLM
anywhere -- deterministic ranking is the source of truth
(MNP_METHODOLOGY_V1 §35). `pure.py`/`feasibility.py`/`transition.py`/
`gap.py`/`ranking.py` are dependency-free (plain dataclasses in, plain
dataclasses out) per this repo's "matching engine is pure/deterministic
where possible" architecture principle; `engine.py` is the only module
that touches SQLAlchemy, converting DB rows to/from the pure layer."""
