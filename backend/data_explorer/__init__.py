"""MNP DATA EXPLORER V1 — a research / data-lab layer for the
«МОЖУ: Мій Напрям» project.

Purpose (see docs/data_explorer/README.md and the workstream brief):
let the Founder, methodologist and developer look at the *real* ESCO and
O*NET data with their own eyes, compare the two, decide what MNP should
use, hand-build MNP Career Profiles and Person Profiles, hand-compare
Person <-> Career, record Human Expected Results, and export a Golden
Dataset + a human-readable Excel workbook.

HARD RULES (brief §24, §27):
  * Dependency direction is one-way:  data_explorer  ->  app.db.models_*
    (read-only).  The production MNP runtime NEVER imports data_explorer.
  * No LLM / AI mapping / AI classification / AI summaries anywhere here.
  * No Ukrainian market layer (Work.ua / robota.ua / ДСЗ / OLX / DOU),
    no Lightcast, no WEF, no scraping.  ESCO + O*NET (+ their official
    crosswalk, + ISCO where it is already a key of those datasets) only.
  * External ids are never MNP primary ids.
  * `UNKNOWN != ABSENT`; a missing numeric value is never treated as 0.
  * This module NEVER edits approved methodology.  A data-driven problem
    with the methodology becomes a METHODOLOGY_FINDING document for the
    Founder to decide on.

Reuse: the O*NET download / tab-file / Scales-Reference-validation logic
originates from commit 6d27bf3 (`scripts/onet_import/`, the prior
data-foundation workstream); it was lifted here and extended, not
rewritten.
"""

from __future__ import annotations

__all__ = ["config", "io"]
