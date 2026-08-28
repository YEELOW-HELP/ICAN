"""Matching V1 M1 -- BASIC_STRUCTURED assessment services.

Architectural zero-AI isolation (Founder Review, 2026-08-28): no module in
this package imports `app.ai_gateway`, or any PRO Hybrid extraction/
synthesis service (`app.services.assessment.extraction`,
`app.services.assessment.cv`, `app.services.assessment.next_question`'s
adaptive-question path, or any Claim Synthesizer). Enforced by
`tests/test_basic_assessment_zero_ai.py`, which fails the build if that
ever silently changes.
"""

from __future__ import annotations
