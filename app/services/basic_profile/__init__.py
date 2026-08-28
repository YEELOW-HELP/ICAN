"""Matching V1 M2 -- deterministic BASIC profile calculation.

Architectural zero-AI isolation (Founder Review, 2026-08-28), same
discipline as `app.services.basic_assessment`: no module in this package
imports `app.ai_gateway`, or any PRO Hybrid extraction/synthesis service.
Enforced by `tests/test_basic_profile_zero_ai.py`.

ZERO LLM TOKENS anywhere in this package -- every value here is pure
arithmetic over already-persisted, already-validated structured answers.
"""

from __future__ import annotations
