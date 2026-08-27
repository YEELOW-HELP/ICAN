"""Deterministic four-output scoring for Direction Intelligence
(Founder decisions F, N + Research Wave A).

Four structurally separate outputs, never blended:
  - Potential Fit          (scoring.components + scoring.aggregate)
  - Goal Alignment         (scoring.components + scoring.aggregate)
  - Transition Feasibility (scoring.components + scoring.skill_state + scoring.aggregate)
  - Evidence Confidence    (scoring.evidence_confidence)

No function here produces a composite career score. No LLM is called.
Missing comparable data -> INSUFFICIENT_DATA, never zero (Founder decision F).
"""
