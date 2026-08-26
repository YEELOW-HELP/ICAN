"""Consent enforcement (Stage 1). Server-side only -- there is no
UI-only consent gate anywhere in this module; `has_active_consent` is
the single function every access-gated flow must call, never a client
flag.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_identity import Consent, GrantorRole
from app.services.events import emit_event

CURRENT_POLICY_VERSION = "v1"
ASSESSMENT_PURPOSE = "assessment_v1"


async def grant_consent(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    purpose: str,
    source: str,
    granted_by_user_id: uuid.UUID | None = None,
    grantor_role: GrantorRole = GrantorRole.SELF,
    policy_version: str = CURRENT_POLICY_VERSION,
) -> Consent:
    """Records a new consent grant. A withdrawal followed by a fresh grant
    is a new row, not a re-activation of the old one -- consent history is
    append-only by construction (no UPDATE ever sets `granted_at`)."""
    consent = Consent(
        user_id=user_id,
        granted_by_user_id=granted_by_user_id or user_id,
        grantor_role=grantor_role,
        purpose=purpose,
        policy_version=policy_version,
        source=source,
    )
    session.add(consent)
    await session.commit()
    await session.refresh(consent)
    emit_event("consent_granted", user_id=str(user_id), purpose=purpose, grantor_role=grantor_role.value)
    return consent


async def withdraw_consent(session: AsyncSession, consent_id: uuid.UUID) -> Consent:
    consent = await session.get(Consent, consent_id)
    if consent is None:
        raise ValueError(f"Consent {consent_id} does not exist")
    if consent.withdrawn_at is None:
        consent.withdrawn_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(consent)
    return consent


async def has_active_consent(session: AsyncSession, *, user_id: uuid.UUID, purpose: str) -> bool:
    """True if the user has ever granted `purpose` and never withdrawn the
    most recent grant. Policy-version changes are not treated as an
    automatic withdrawal in Stage 1 -- re-consent-on-policy-change is a
    Stage 2+/legal-review decision, not assumed here."""
    result = await session.execute(
        select(Consent)
        .where(Consent.user_id == user_id, Consent.purpose == purpose)
        .order_by(Consent.granted_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    return latest is not None and latest.withdrawn_at is None
