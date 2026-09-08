"""Security/RBAC checklist for Stage 1 (Section 21): ownership is
enforced on every session-scoped command via the single
get_owned_session() choke point (app/services/assessment/sessions.py),
not re-implemented ad hoc per command. test_assessment_answers.py already
proves this for submit_answer; this file proves the same guarantee holds
for the other session-scoped commands so a future refactor that bypasses
get_owned_session() for one of them fails loudly here.
"""

import pytest

from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_identity import IdentityUser
from app.services.assessment.sessions import (
    complete_assessment,
    get_next_question_for_session,
    pause_assessment,
    resume_assessment,
    start_assessment,
    submit_answer,
)
from app.services.exceptions import AssessmentOwnershipError
from app.services.product_access import grant_manual_access


async def _make_two_users_and_a_session(session):
    owner = IdentityUser()
    intruder = IdentityUser()
    session.add_all([owner, intruder])
    await session.flush()
    admin = AdminUser(email="sec-admin@test.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
    session.add(admin)
    await session.commit()
    await session.refresh(owner)
    await session.refresh(intruder)
    await session.refresh(admin)
    await grant_manual_access(session, user_id=owner.id, plan_code="BASIC", granted_by_admin=admin)
    interview_session = await start_assessment(session, user_id=owner.id, plan_code="BASIC")
    return owner, intruder, interview_session


async def test_intruder_cannot_pause_another_users_session(session_factory):
    async with session_factory() as session:
        owner, intruder, interview_session = await _make_two_users_and_a_session(session)
        with pytest.raises(AssessmentOwnershipError):
            await pause_assessment(session, session_id=interview_session.id, user_id=intruder.id)


async def test_intruder_cannot_resume_another_users_session(session_factory):
    async with session_factory() as session:
        owner, intruder, interview_session = await _make_two_users_and_a_session(session)
        await submit_answer(
            session, session_id=interview_session.id, user_id=owner.id, question_id="current_status",
            raw_text="working", idempotency_key="k1", source="telegram",
        )
        await pause_assessment(session, session_id=interview_session.id, user_id=owner.id)
        with pytest.raises(AssessmentOwnershipError):
            await resume_assessment(session, session_id=interview_session.id, user_id=intruder.id)


async def test_intruder_cannot_read_another_users_next_question(session_factory):
    async with session_factory() as session:
        owner, intruder, interview_session = await _make_two_users_and_a_session(session)
        with pytest.raises(AssessmentOwnershipError):
            await get_next_question_for_session(session, session_id=interview_session.id, user_id=intruder.id)


async def test_intruder_cannot_complete_another_users_session(session_factory):
    async with session_factory() as session:
        owner, intruder, interview_session = await _make_two_users_and_a_session(session)
        with pytest.raises(AssessmentOwnershipError):
            await complete_assessment(session, session_id=interview_session.id, user_id=intruder.id)


async def test_unprivileged_admin_cannot_grant_access_even_to_their_own_user(session_factory):
    """An ADMIN-MANAGER-only or unprivileged role must not be able to
    self-grant access by targeting their own user_id -- the role check in
    grant_manual_access has no special case for "granting to yourself"."""
    async with session_factory() as session:
        user = IdentityUser()
        session.add(user)
        await session.flush()
        unprivileged = AdminUser(email="reviewer@test.dev", password_hash=hash_password("pw"), role=AdminRole.REVIEWER)
        session.add(unprivileged)
        await session.commit()
        await session.refresh(user)
        await session.refresh(unprivileged)

        from app.services.exceptions import InsufficientRoleError

        with pytest.raises(InsufficientRoleError):
            await grant_manual_access(session, user_id=user.id, plan_code="BASIC", granted_by_admin=unprivileged)
