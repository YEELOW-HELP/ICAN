from app.db.models import MessageRole, ScreeningState
from app.schemas.profile import ProfileDraft
from app.services import profile_service


async def test_get_or_create_user_is_idempotent(session):
    user1 = await profile_service.get_or_create_user(session, telegram_id=42)
    user2 = await profile_service.get_or_create_user(session, telegram_id=42)
    assert user1.id == user2.id
    assert user1.screening_state == ScreeningState.NOT_STARTED


async def test_get_or_create_user_creates_empty_profile(session):
    user = await profile_service.get_or_create_user(session, telegram_id=1)
    profile = await profile_service.get_profile(session, user)
    assert profile.name is None
    assert profile.confirmed is False


async def test_apply_profile_draft_only_sets_given_fields(session):
    user = await profile_service.get_or_create_user(session, telegram_id=2)
    draft = ProfileDraft(name="Олена", city="Харків")
    profile = await profile_service.apply_profile_draft(session, user, draft)
    assert profile.name == "Олена"
    assert profile.city == "Харків"
    assert profile.country is None


async def test_confirm_profile_sets_flags(session):
    user = await profile_service.get_or_create_user(session, telegram_id=3)
    profile = await profile_service.confirm_profile(session, user)
    assert profile.confirmed is True
    assert user.screening_state == ScreeningState.CONFIRMED


async def test_record_message_and_get_messages_preserve_order(session):
    user = await profile_service.get_or_create_user(session, telegram_id=4)
    await profile_service.record_message(session, user, MessageRole.USER, "Привіт")
    await profile_service.record_message(session, user, MessageRole.ASSISTANT, "Вітаю!")
    messages = await profile_service.get_messages(session, user)
    assert [m.content for m in messages] == ["Привіт", "Вітаю!"]
