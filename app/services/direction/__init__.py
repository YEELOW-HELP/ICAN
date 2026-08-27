"""Direction Intelligence (Stage 3B).

The bounded module that compares a Human Potential Profile (Stage 2) to
the Career Knowledge Base (Stage 3A) and produces career directions --
under the Founder-approved methodology contract in `methodology_lab/`.

Slice 1 (this commit) is deterministic-only foundation:
- `versions`             -- version constants stamped on every artifact
- `dimensions`           -- the 12 canonical MNP dimensions + v0.1 subdimensions
- `dimension_mapping`    -- legacy ProfileClaim -> canonical, versioned adapter
- `config`               -- versioned EXPERIMENTAL ScoringConfig
- `constraints`          -- ProfileConstraint derivation + deterministic hard-constraint gate
- `fit`                  -- deterministic Fit component interfaces + v0.1 scorers + aggregation
- `confidence`           -- deterministic direction-confidence (LOW/MEDIUM/HIGH)
- `threshold`            -- deterministic minimum-profile gate

Not in Slice 1 (Founder scope): LLM narrative, LLM critic, final ranking
orchestration, consultant-review API/UI, Route Builder, report, PDF.
"""
