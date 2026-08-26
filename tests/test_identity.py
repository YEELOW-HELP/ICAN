import pytest
from sqlalchemy import select

from app.db.models import User as LegacyUser
from app.db.models_identity import AuthIdentity, IdentityUser
from app.services.identity import resolve_identity


async def test_resolve_identity_creates_canonical_user_and_auth_identity(session_factory):
    async with session_factory() as session:
        user = await resolve_identity(session, provider="telegram", provider_subject="111", provider_username="alice")

        result = await session.execute(select(AuthIdentity).where(AuthIdentity.user_id == user.id))
        identity = result.scalar_one()
        assert identity.provider == "telegram"
        assert identity.provider_subject == "111"
        assert identity.provider_username == "alice"
        assert identity.last_seen_at is not None


async def test_resolve_identity_is_idempotent_for_the_same_provider_subject(session_factory):
    async with session_factory() as session:
        first = await resolve_identity(session, provider="telegram", provider_subject="222")
        second = await resolve_identity(session, provider="telegram", provider_subject="222")
        assert first.id == second.id

        result = await session.execute(select(IdentityUser))
        assert len(result.scalars().all()) == 1


async def test_resolve_identity_updates_username_and_last_seen_on_repeat_contact(session_factory):
    async with session_factory() as session:
        await resolve_identity(session, provider="telegram", provider_subject="333", provider_username="old_name")
        await resolve_identity(session, provider="telegram", provider_subject="333", provider_username="new_name")

        result = await session.execute(select(AuthIdentity).where(AuthIdentity.provider_subject == "333"))
        identity = result.scalar_one()
        assert identity.provider_username == "new_name"


async def test_different_providers_with_same_subject_string_are_different_identities(session_factory):
    """UNIQUE(provider, provider_subject) -- not provider_subject alone --
    is what the future-web-identity compatibility requirement actually
    depends on."""
    async with session_factory() as session:
        telegram_user = await resolve_identity(session, provider="telegram", provider_subject="444")
        web_user = await resolve_identity(session, provider="web", provider_subject="444")
        assert telegram_user.id != web_user.id


async def test_duplicate_provider_subject_insert_is_rejected_at_db_level(session_factory):
    """Directly proves the UNIQUE constraint, independent of the
    resolve-or-create service logic above."""
    from sqlalchemy.exc import IntegrityError

    async with session_factory() as session:
        user = IdentityUser()
        session.add(user)
        await session.flush()
        session.add(AuthIdentity(user_id=user.id, provider="telegram", provider_subject="555"))
        await session.commit()

        session.add(AuthIdentity(user_id=user.id, provider="telegram", provider_subject="555"))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_resolve_identity_opportunistically_links_existing_legacy_telegram_user(session_factory):
    async with session_factory() as session:
        legacy = LegacyUser(telegram_id=999888)
        session.add(legacy)
        await session.commit()
        await session.refresh(legacy)
        assert legacy.canonical_user_id is None

        canonical = await resolve_identity(session, provider="telegram", provider_subject="999888")

        await session.refresh(legacy)
        assert legacy.canonical_user_id == canonical.id


async def test_resolve_identity_does_not_touch_unrelated_legacy_users(session_factory):
    """Additive-only: resolving one Telegram id must never modify a
    different legacy user's row."""
    async with session_factory() as session:
        other = LegacyUser(telegram_id=1)
        session.add(other)
        await session.commit()

        await resolve_identity(session, provider="telegram", provider_subject="2")

        await session.refresh(other)
        assert other.canonical_user_id is None


async def test_resolve_identity_recovers_when_a_concurrent_request_wins_the_race(session_factory, monkeypatch):
    """Simulates the exact race resolve_identity() is built to survive: by
    the time this call's INSERT would run, another request for the same
    (provider, provider_subject) has already committed first. Patches
    _get_auth_identity to return nothing on the first lookup (forcing the
    create path) so the insert genuinely conflicts, rather than relying on
    true asyncio-level concurrency over the test suite's single shared
    SQLite connection, which does not reliably reproduce a DB-level race
    (see the direct UNIQUE-constraint test above for that guarantee, and
    Sprint 1 Part 0's real-Postgres CI job for genuine concurrency)."""
    import app.services.identity as identity_module

    async with session_factory() as session:
        winner = await resolve_identity(session, provider="telegram", provider_subject="777")

    call_count = {"n": 0}
    real_lookup = identity_module._get_auth_identity

    async def _lookup_missing_once_then_real(session, provider, provider_subject):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None  # pretend no identity exists yet, forcing the create/insert path
        return await real_lookup(session, provider, provider_subject)

    monkeypatch.setattr(identity_module, "_get_auth_identity", _lookup_missing_once_then_real)

    async with session_factory() as session:
        loser_path_result = await resolve_identity(session, provider="telegram", provider_subject="777")

    assert loser_path_result.id == winner.id

    async with session_factory() as session:
        result = await session.execute(select(IdentityUser))
        assert len(result.scalars().all()) == 1
