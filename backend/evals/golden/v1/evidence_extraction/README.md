# Evidence Extraction (`target: "evidence_extraction"`)

Four cases (Stage 2, Issue #2) covering the Evidence Extractor
(`docs/architecture/04_AI_SYSTEM.md` component #2 —
`app/services/profile/evidence_extraction.py`): a straightforward
coherent signal, a CV-heavy answer (direct facts, not personality
inference), an open-answer-heavy answer producing multiple distinct
evidence items, and a sparse/low-information answer that must correctly
yield zero evidence rather than a fabricated one. See
`evals/golden/README.md` for governance/review rules — all four are
`status: draft`, not yet reviewed.
