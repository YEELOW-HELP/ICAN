"""Evidence-level (E1-E3) classification (MNP Evidence Standard v0.1
section 1.1), the missing piece Slice 1 deliberately left for the
orchestrator: `scoring/evidence_confidence.py` consumes a pre-computed
`dominant_evidence_tier` string, but nothing in Slice 1 computed one from
real `Evidence` rows -- that requires DB access the pure scoring layer was
built to avoid (`ScoreContext` is deliberately ORM-free).

Computed, never assigned by an LLM. v0.1 rule (Evidence Standard 1.1):

| condition                                                        | level |
|-------------------------------------------------------------------|-------|
| >= 2 independent items, >= 1 direct (structured_answer/cv/deterministic), no contradiction | E3 |
| exactly 1 direct item, or >= 2 consistent open_answer items       | E2    |
| exactly 1 open_answer/llm_extraction item                         | E1    |
| contradiction present                                              | not levelled (CONTRADICTED) |

`E0` cannot occur here: every `Evidence` row is source-referenced and a
zero-evidence claim is never persisted by Stage 2 (`compute_claim_confidence`
returns `None` in that case) -- there is nothing to classify.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.db.models_profile import Evidence

__all__ = ["classify_evidence_tier", "dominant_tier", "TIER_ORDER"]

_DIRECT_SOURCE_TYPES = {"structured_answer", "cv"}

TIER_ORDER = ("E1", "E2", "E3")


def classify_evidence_tier(evidence_items: Sequence[Evidence], *, is_contradictory: bool) -> str | None:
    """One claim's evidence tier. `None` when there is nothing to level
    (no evidence, or the claim is contradictory -- contradictions are
    handled as `CONTRADICTED`, not levelled, per the table above)."""
    if is_contradictory or not evidence_items:
        return None

    direct_count = sum(
        1 for e in evidence_items if e.source_type.value in _DIRECT_SOURCE_TYPES or e.extraction_method == "deterministic"
    )
    open_answer_count = sum(1 for e in evidence_items if e.source_type.value == "open_answer")

    if len(evidence_items) >= 2 and direct_count >= 1:
        return "E3"
    if direct_count >= 1 or open_answer_count >= 2:
        return "E2"
    return "E1"


def dominant_tier(tiers: Sequence[str | None]) -> str | None:
    """The strongest tier among a set of per-claim tiers (E3 > E2 > E1);
    `None` if none of them could be levelled."""
    present = [t for t in tiers if t is not None]
    if not present:
        return None
    return max(present, key=TIER_ORDER.index)
