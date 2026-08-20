from app.db.models_crm import ClientStatus, SourceChannel
from app.schemas.profile import ProfileDraft
from app.services import profile_service
from app.services.crm import clients as client_service


async def test_bot_confirmation_creates_linked_client(session):
    user = await profile_service.get_or_create_user(session, telegram_id=555, telegram_username="olena")
    await profile_service.apply_profile_draft(
        session,
        user,
        ProfileDraft(
            name="Олена Ковальчук",
            city="Харків",
            country="Україна",
            desired_role="бухгалтер",
            desired_min_income="35000",
            desired_currency="грн",
            employment_format="full-time",
            work_format="remote",
            skills=["1С", "Excel"],
            languages=["українська", "англійська"],
            status="не працює",
        ),
    )

    await profile_service.confirm_profile(session, user)

    client = await client_service.get_client_by_telegram_user(session, user.id)

    assert client is not None
    assert client.first_name == "Олена"
    assert client.last_name == "Ковальчук"
    assert client.city == "Харків"
    assert client.source_channel == SourceChannel.TELEGRAM
    # bot already did the "first screening" — skip straight past NEW/SCREENING
    assert client.status == ClientStatus.WAITING_CONSULTANT
    assert client.profile.primary_target == "бухгалтер"
    assert client.profile.min_salary == "35000"
    assert client.profile.currently_employed is False
    assert {s.skill_name for s in client.skills} == {"1С", "Excel"}
    assert {l.language for l in client.languages} == {"українська", "англійська"}


async def test_bot_reconfirmation_updates_existing_client_without_duplicating(session):
    user = await profile_service.get_or_create_user(session, telegram_id=556)
    await profile_service.apply_profile_draft(session, user, ProfileDraft(name="Іван", city="Київ"))
    await profile_service.confirm_profile(session, user)

    await profile_service.apply_profile_draft(session, user, ProfileDraft(name="Іван", city="Львів"))
    await profile_service.confirm_profile(session, user)

    rows, total = await client_service.list_clients(
        session, viewer=await _admin(session)
    )
    assert total == 1
    assert rows[0].city == "Львів"


async def _admin(session):
    from app.core.security import hash_password
    from app.db.models import AdminRole, AdminUser

    admin = AdminUser(email="a@ican.dev", password_hash=hash_password("pw"), role=AdminRole.ADMIN)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin
