"""Matching V1 M2 -- determinism, immutability, retake, identity (Founder
Review test items #22-25)."""

import dataclasses

from app.services.basic_assessment.attempts import complete_attempt
from app.services.basic_assessment.seed import seed_alpha_long_form
from app.services.basic_profile.calculation import calculate_basic_profile
from app.services.basic_profile.contract import build_basic_profile_result
from app.services.basic_profile.queries import get_basic_profile
from tests.helpers_basic_profile import answer_all_items


def _strip_provenance(result):
    """Everything except timestamps/DB IDs -- i.e. every field a second,
    independent calculation over the same answers must reproduce exactly."""
    d = dataclasses.asdict(result)
    d.pop("provenance")
    return d


async def test_same_answers_produce_identical_result(session):
    """#22 -- golden deterministic fixture: two DIFFERENT users answering
    identically produce structurally identical profiles (excluding
    timestamps/DB IDs/user identity)."""
    definition = await seed_alpha_long_form(session)
    bias = {
        ("riasec", "R"): 5, ("riasec", "I"): 4, ("riasec", "A"): 2,
        ("work_style", "leadership"): 5, ("work_values", "growth"): 4,
    }

    attempt_a, _user_a = await answer_all_items(session, definition, likert_bias=bias)
    await complete_attempt(session, attempt_a)
    await session.commit()
    profile_a = await calculate_basic_profile(session, attempt_a)
    await session.commit()

    attempt_b, _user_b = await answer_all_items(session, definition, likert_bias=bias)
    await complete_attempt(session, attempt_b)
    await session.commit()
    profile_b = await calculate_basic_profile(session, attempt_b)
    await session.commit()

    result_a = await build_basic_profile_result(session, profile_a)
    result_b = await build_basic_profile_result(session, profile_b)

    assert _strip_provenance(result_a) == _strip_provenance(result_b)

    # and re-running the calculation over the SAME attempt again is a pure no-op
    profile_a_again = await calculate_basic_profile(session, attempt_a)
    assert profile_a_again.id == profile_a.id


async def test_historical_profile_immutable_after_retake(session):
    """#23."""
    definition = await seed_alpha_long_form(session)
    attempt1, user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt1)
    await session.commit()
    profile1 = await calculate_basic_profile(session, attempt1)
    await session.commit()

    original_coverage = profile1.coverage
    original_calculated_at = profile1.calculated_at

    # retake
    attempt2, _ = await answer_all_items(session, definition, user=user)
    await complete_attempt(session, attempt2)
    await session.commit()
    await calculate_basic_profile(session, attempt2)
    await session.commit()

    await session.refresh(profile1)
    assert profile1.coverage == original_coverage
    # SQLite (unlike Postgres) drops tzinfo on a DateTime(timezone=True)
    # round-trip -- compare naive-vs-naive so this assertion is about
    # value immutability, not a SQLite-only serialization detail.
    assert profile1.calculated_at.replace(tzinfo=None) == original_calculated_at.replace(tzinfo=None)
    assert profile1.is_current is False  # superseded, but fields untouched


async def test_retake_creates_separate_profile(session):
    """#24."""
    definition = await seed_alpha_long_form(session)
    attempt1, user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt1)
    await session.commit()
    profile1 = await calculate_basic_profile(session, attempt1)
    await session.commit()

    attempt2, _ = await answer_all_items(session, definition, user=user)
    await complete_attempt(session, attempt2)
    await session.commit()
    profile2 = await calculate_basic_profile(session, attempt2)
    await session.commit()

    assert profile2.id != profile1.id
    assert profile2.attempt_id != profile1.attempt_id
    assert profile2.is_current is True

    current = await get_basic_profile(session, user.id)
    assert current.id == profile2.id


async def test_canonical_identity_user_preserved(session):
    """#25 -- the profile is attached directly to IdentityUser.id, no
    separate BASIC-only identity concept is created."""
    definition = await seed_alpha_long_form(session)
    attempt, user = await answer_all_items(session, definition)
    await complete_attempt(session, attempt)
    await session.commit()
    profile = await calculate_basic_profile(session, attempt)
    await session.commit()

    assert profile.user_id == user.id
