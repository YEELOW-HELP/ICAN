"""Stage 4A.5 §2: the Stage 1 -> Stage 2 profile-generation bridge, driven
through the REAL registered bot handlers (the same BotHarness technique
tests/test_bot_v1_e2e.py already uses) -- proves the bridge actually
fires from a real completed conversation, not just at the service layer.
"""

from __future__ import annotations

import functools

from app.bot.handlers_v1 import register_handlers_v1
from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.models_profile import ProfileGenerationStatus
from app.services.assessment.extraction import ExtractionResult
from app.services.identity import resolve_identity
from app.services.product_access import create_package_allocation, issue_promo_code
from app.services.profile.generation import get_current_profile
from tests.bot_harness import BotHarness
from tests.profile_test_helpers import FakeClaimSynthesizer, FakeEvidenceExtractor, FakeSummarizer
from tests.test_bot_v1_e2e import REQUIRED_ANSWERS, ScriptedExtractor


async def _make_promo(session_factory, *, email: str):
    async with session_factory() as session:
        admin = AdminUser(email=email, password_hash=hash_password("pw"), role=AdminRole.ADMIN)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        allocation = await create_package_allocation(session, plan_code="BASIC", total_quantity=5, created_by_admin=admin)
        return await issue_promo_code(session, allocation_id=allocation.id, issued_by_admin=admin)


async def _complete_assessment_via_harness(harness: BotHarness, telegram_id: int, promo_code: str) -> None:
    await harness.send_text(telegram_id, "/start")
    await harness.click(telegram_id, "v1consent:agree")
    await harness.send_text(telegram_id, promo_code)
    await harness.click(telegram_id, "v1cv:skip")
    await harness.send_text(telegram_id, REQUIRED_ANSWERS["name"])
    await harness.send_text(telegram_id, REQUIRED_ANSWERS["city"])
    await harness.click(telegram_id, f"v1c:{REQUIRED_ANSWERS['current_status']}")
    await harness.send_text(telegram_id, REQUIRED_ANSWERS["key_skills_or_interests"])
    await harness.send_text(telegram_id, REQUIRED_ANSWERS["desired_direction_hint"])


# ---------------------------------------------------------------- 1, 6


async def test_completing_assessment_triggers_profile_generation_via_bridge(session_factory):
    """#1 + #6: a real completed conversation (via the real registered
    handlers) leaves a READY PotentialProfile behind, for the SAME
    canonical IdentityUser the bot resolved from the telegram_id -- no
    separate manual "generate profile" step required."""
    promo = await _make_promo(session_factory, email="bridge-admin1@test.dev")
    extractor = ScriptedExtractor()
    register_fn = functools.partial(
        register_handlers_v1,
        evidence_extractor_factory=lambda: FakeEvidenceExtractor(),
        claim_synthesizer_factory=lambda: FakeClaimSynthesizer(),
        summarizer_factory=lambda: FakeSummarizer(),
    )
    harness = BotHarness(session_factory, lambda: extractor, register_fn=register_fn)
    telegram_id = 6001

    await _complete_assessment_via_harness(harness, telegram_id, promo.code)
    assert "завершено" in harness.last_sent_text().lower()  # bridge fires AFTER this message, never delays it

    async with session_factory() as session:
        user = await resolve_identity(session, provider="telegram", provider_subject=str(telegram_id))
        profile = await get_current_profile(session, user_id=user.id)
        assert profile is not None
        assert profile.status is ProfileGenerationStatus.READY
        assert profile.user_id == user.id  # canonical IdentityUser mapping preserved end-to-end


# ---------------------------------------------------------------- 3


async def test_bridge_failure_does_not_crash_handler_and_is_retryable(session_factory):
    """#3: if the synchronous bridge call raises, the bot keeps working
    (the "completed" message was already sent) and the admin fallback can
    retry afterward -- a FAILED attempt is never `is_current`."""
    from tests.profile_test_helpers import ExplodingEvidenceExtractor

    promo = await _make_promo(session_factory, email="bridge-admin2@test.dev")
    extractor = ScriptedExtractor()
    register_fn = functools.partial(
        register_handlers_v1,
        evidence_extractor_factory=lambda: ExplodingEvidenceExtractor(RuntimeError("simulated extraction outage")),
    )
    harness = BotHarness(session_factory, lambda: extractor, register_fn=register_fn)
    telegram_id = 6002

    await _complete_assessment_via_harness(harness, telegram_id, promo.code)
    assert "завершено" in harness.last_sent_text().lower()  # handler did not crash

    async with session_factory() as session:
        user = await resolve_identity(session, provider="telegram", provider_subject=str(telegram_id))
        profile = await get_current_profile(session, user_id=user.id)
        assert profile is None  # the failed attempt never became current

    from app.services.profile.generation import generate_profile_for_user

    async with session_factory() as session:
        user = await resolve_identity(session, provider="telegram", provider_subject=str(telegram_id))
        retried = await generate_profile_for_user(
            session, user_id=user.id, evidence_extractor=FakeEvidenceExtractor(),
            claim_synthesizer=FakeClaimSynthesizer(), summarizer=FakeSummarizer(),
        )
        assert retried.status is ProfileGenerationStatus.READY
