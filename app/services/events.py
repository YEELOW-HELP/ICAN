"""Minimal canonical event emission (Stage 1 -- Issue #8's event envelope,
docs/architecture/03_API_AND_EVENTS.md). Structured-logged, not persisted
to a table -- the same scoping call already made for `AI_TRACE`
(Sprint 0 Part 4): the shape is real and stable, persistence/warehousing is
Stage 4 (Analytics) work, not invented speculatively here.

`emit_event` never raises: a logging failure must not break the business
transaction it's reporting on (explicit Stage 1 requirement). Call it
after the transaction that matters has already committed, not instead of
committing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("app.events")

EVENT_ENVELOPE_VERSION = 1


def emit_event(
    event_name: str,
    *,
    user_id: str | uuid.UUID | None = None,
    session_id: str | uuid.UUID | None = None,
    trace_id: str | None = None,
    source: str = "telegram",
    **properties: Any,
) -> None:
    try:
        logger.info(
            "product_event name=%s version=%d event_id=%s occurred_at=%s user_id=%s session_id=%s trace_id=%s source=%s properties=%r",
            event_name,
            EVENT_ENVELOPE_VERSION,
            uuid.uuid4(),
            datetime.now(timezone.utc).isoformat(),
            user_id,
            session_id,
            trace_id,
            source,
            properties,
        )
    except Exception:
        # Analytics must never take down the request/flow that triggered it.
        logger.exception("Failed to emit product event %s (non-fatal)", event_name)
