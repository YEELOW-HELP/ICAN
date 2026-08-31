"""MNP V1 BLOCK A -- CareerCard core-domain: one master card per user,
evidence recording, versioned snapshotting."""

import uuid

from app.db.models_career_card import (
    EntryMode,
    EvidenceSourceType,
    EvidenceType,
    MnpExperience,
    SourceMode,
)
from app.db.models_identity import IdentityUser
from app.services.career_card_mnp.card import (
    get_or_create_career_card,
    record_evidence,
    snapshot_career_card,
    start_assessment_session,
)


async def _make_user(session) -> IdentityUser:
    user = IdentityUser(locale="uk")
    session.add(user)
    await session.flush()
    return user


async def test_one_career_card_per_user(session):
    user = await _make_user(session)
    s1 = await start_assessment_session(session, user_id=user.id, entry_mode=EntryMode.MANUAL)
    card1 = await get_or_create_career_card(session, user_id=user.id, assessment_session_id=s1.id, source_mode=SourceMode.MANUAL)
    await session.commit()

    s2 = await start_assessment_session(session, user_id=user.id, entry_mode=EntryMode.RESUME)
    card2 = await get_or_create_career_card(session, user_id=user.id, assessment_session_id=s2.id, source_mode=SourceMode.RESUME)
    await session.commit()

    assert card1.id == card2.id  # same master card, not a duplicate
    assert card2.source_mode == SourceMode.MIXED  # manual then resume -> mixed
    assert card2.assessment_session_id == s2.id  # retargeted to the latest session


async def test_evidence_recorded_as_claimed_not_verified_by_default(session):
    user = await _make_user(session)
    s1 = await start_assessment_session(session, user_id=user.id, entry_mode=EntryMode.MANUAL)
    card = await get_or_create_career_card(session, user_id=user.id, assessment_session_id=s1.id, source_mode=SourceMode.MANUAL)
    await session.commit()

    evidence = await record_evidence(
        session, card, entity_type="person_skill", entity_id=uuid.uuid4(), evidence_type=EvidenceType.CLAIMED,
        source_type=EvidenceSourceType.QUESTIONNAIRE,
    )
    await session.commit()
    assert evidence.evidence_type == EvidenceType.CLAIMED


async def test_snapshot_captures_full_card_and_bumps_version(session):
    user = await _make_user(session)
    s1 = await start_assessment_session(session, user_id=user.id, entry_mode=EntryMode.MANUAL)
    card = await get_or_create_career_card(session, user_id=user.id, assessment_session_id=s1.id, source_mode=SourceMode.MANUAL)
    session.add(MnpExperience(
        career_card_id=card.id, raw_job_title="Sales Manager", source_type=EvidenceSourceType.QUESTIONNAIRE,
        confidence=1.0,
    ))
    await session.flush()
    await session.commit()

    assert card.version == 1
    version_row = await snapshot_career_card(session, card)
    await session.commit()

    assert card.version == 2
    assert version_row.version == 2
    assert len(version_row.snapshot["experiences"]) == 1
    assert version_row.snapshot["experiences"][0]["raw_job_title"] == "Sales Manager"

    # A second snapshot bumps again, and both remain independently readable.
    version_row_2 = await snapshot_career_card(session, card)
    await session.commit()
    assert version_row_2.version == 3
    assert version_row.version == 2  # first snapshot untouched
