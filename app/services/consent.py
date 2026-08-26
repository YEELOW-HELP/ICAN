"""Consent enforcement (Stage 1). Server-side only -- there is no
UI-only consent gate anywhere in this module; `has_active_consent` is
the single function every access-gated flow must call, never a client
flag.

Consent *grants* are immutable history (a withdrawal followed by a fresh
grant is always a new row -- `granted_at` is never touched by an UPDATE).
The table as a whole is not strictly append-only, though: withdrawal is
an explicit, ownership-checked state change that mutates `withdrawn_at`
on the existing row rather than inserting a new one. Describing the
whole table as "append-only" would overstate the guarantee (Founder
hardening review, item 6)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminRole, AdminUser
from app.db.models_identity import Consent, GrantorRole
from app.services.audit import record_audit
from app.services.events import emit_event
from app.services.exceptions import ConsentOwnershipError, InsufficientRoleError

CURRENT_POLICY_VERSION = "v1"
ASSESSMENT_PURPOSE = "assessment_v1"

_ADMIN_WITHDRAWAL_ROLES = {AdminRole.SUPER_ADMIN, AdminRole.ADMIN, AdminRole.MANAGER}


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
    is a new row, not a re-activation of the old one -- see the module
    docstring for why the table as a whole is not called "append-only.\""""
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


async def withdraw_consent(
    session: AsyncSession,
    consent_id: uuid.UUID,
    *,
    requested_by_user_id: uuid.UUID | None = None,
    requested_by_admin: AdminUser | None = None,
) -> Consent:
    """Ownership-checked (Founder hardening review, item 6): there is no
    way to withdraw an arbitrary consent by ID with no actor. A user may
    withdraw only their own consent (`requested_by_user_id` must match
    `Consent.user_id`); an admin may withdraw on a user's behalf only
    with a sufficient role (`SUPER_ADMIN`/`ADMIN`/`MANAGER`), and that
    privileged action is audit-logged -- self-withdrawal by the owning
    user is not (it's the user's own data, not a privileged operation)."""
    consent = await session.get(Consent, consent_id)
    if consent is None:
        raise ValueError(f"Consent {consent_id} does not exist")

    if requested_by_admin is not None:
        if requested_by_admin.role not in _ADMIN_WITHDRAWAL_ROLES:
            raise InsufficientRoleError(f"role {requested_by_admin.role.value} may not withdraw another user's consent")
    elif requested_by_user_id is not None:
        if requested_by_user_id != consent.user_id:
            raise ConsentOwnershipError(f"user {requested_by_user_id} does not own consent {consent_id}")
    else:
        raise ConsentOwnershipError(
            "withdraw_consent requires an authorized actor (requested_by_user_id or requested_by_admin)"
        )

    if consent.withdrawn_at is None:
        consent.withdrawn_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(consent)
        emit_event("consent_withdrawn", user_id=str(consent.user_id), purpose=consent.purpose)
        if requested_by_admin is not None:
            await record_audit(
                session,
                entity_type="consent",
                entity_id=str(consent.id),
                action="withdraw",
                actor_admin_id=requested_by_admin.id,
                actor_user_id=consent.user_id,
            )
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
