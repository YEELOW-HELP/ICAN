# Profile Synthesis (`target: "profile_synthesis"`)

Five cases (Stage 2, Issue #2) covering the Profile Synthesizer
(`docs/architecture/04_AI_SYSTEM.md` component #3 —
`app/services/profile/claim_synthesis.py`): contradictory evidence
retained (never silently averaged), a hard constraint preserved without
softening, no hallucinated salary/market data, no diagnosis/clinical
language, and no unsupported personality claim from a single weak
evidence item. See `evals/golden/README.md` for governance/review rules —
all five are `status: draft`, not yet reviewed.
