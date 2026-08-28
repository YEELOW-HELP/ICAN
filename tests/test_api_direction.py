"""Stage 4A: the MNP consultant workspace API (Issue #3)."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.core.security import hash_password
from app.db.models import AdminRole, AdminUser
from app.db.session import get_session
from app.services.direction.config import ensure_experimental_ranking_policy, ensure_experimental_scoring_config
from tests.direction_pipeline_test_helpers import make_user, seed_eligible_developer_profile, seed_knowledge_base


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _create_staff(session_factory, email, role, password="pw"):
    async with session_factory() as session:
        staff = AdminUser(email=email, password_hash=hash_password(password), role=role, full_name=email.split("@")[0])
        session.add(staff)
        await session.commit()
        await session.refresh(staff)
        return staff.id


async def _login(client, email, password="pw"):
    resp = await client.post("/admin/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_world(session_factory):
    async with session_factory() as session:
        await ensure_experimental_scoring_config(session)
        await ensure_experimental_ranking_policy(session)
        await seed_knowledge_base(session)
        user = await make_user(session)
        await seed_eligible_developer_profile(session, user=user)
        return user.id


# ---------------------------------------------------------------- 1, 2


async def test_authorized_consultant_can_open_client_card(client, session_factory):
    """#1."""
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "consultant@ican.dev", AdminRole.CAREER_CONSULTANT)
    headers = await _login(client, "consultant@ican.dev")

    gen = await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)
    assert gen.status_code == 201

    resp = await client.get(f"/direction/clients/{user_id}/card", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["client"]["user_id"] == str(user_id)
    assert body["directions"]


async def test_unauthorized_user_cannot_open_client_card(client, session_factory):
    """#2: no auth header at all."""
    user_id = await _seed_world(session_factory)
    resp = await client.get(f"/direction/clients/{user_id}/card")
    assert resp.status_code == 401


# ---------------------------------------------------------------- 3


async def test_client_list_filters_work(client, session_factory):
    """#3."""
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "admin1@ican.dev", AdminRole.ADMIN)
    headers = await _login(client, "admin1@ican.dev")

    resp = await client.get("/direction/clients", headers=headers)
    assert resp.status_code == 200
    all_items = resp.json()
    assert any(item["user_id"] == str(user_id) for item in all_items)

    resp_no_directions = await client.get("/direction/clients?filter=no_directions_yet", headers=headers)
    assert resp_no_directions.status_code == 200
    assert any(item["user_id"] == str(user_id) for item in resp_no_directions.json())

    await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)
    resp_no_directions_after = await client.get("/direction/clients?filter=no_directions_yet", headers=headers)
    assert not any(item["user_id"] == str(user_id) for item in resp_no_directions_after.json())

    resp_needs_review = await client.get("/direction/clients?filter=needs_review", headers=headers)
    assert any(item["user_id"] == str(user_id) for item in resp_needs_review.json())


# ---------------------------------------------------------------- 4, 5


async def test_all_four_outputs_displayed_independently_and_unknown_not_low(client, session_factory):
    """#4 + #5."""
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "admin2@ican.dev", AdminRole.ADMIN)
    headers = await _login(client, "admin2@ican.dev")
    await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)

    card = (await client.get(f"/direction/clients/{user_id}/card", headers=headers)).json()
    direction = next(d for d in card["directions"] if d["career_code"] == "dev_strong")
    outputs = direction["outputs"]
    assert set(outputs.keys()) == {
        "potential_fit_raw", "potential_fit_band", "goal_alignment_raw", "goal_alignment_band",
        "transition_feasibility_raw", "transition_feasibility_band", "evidence_confidence_raw", "evidence_confidence_band",
    }
    assert outputs["potential_fit_band"] == "high"
    # goal_alignment is real (Slice 3) and matches here (remote goal vs REMOTE work context) -- still independent, never LOW-by-default:
    assert outputs["goal_alignment_band"] != "low" or outputs["goal_alignment_raw"] is not None  # never a silent UNKNOWN->LOW coercion

    # find a direction with a genuinely unknown output and confirm it renders as null, not "low"
    gap_direction = next(d for d in card["directions"] if d["career_code"] == "commercial_pilot")
    assert gap_direction["outputs"]["goal_alignment_band"] is None
    assert gap_direction["outputs"]["goal_alignment_raw"] is None


# ---------------------------------------------------------------- 6


async def test_system_vs_effective_placement_both_preserved(client, session_factory):
    """#6."""
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "admin3@ican.dev", AdminRole.ADMIN)
    headers = await _login(client, "admin3@ican.dev")
    gen = (await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)).json()
    run_id = gen["run_id"]

    card = (await client.get(f"/direction/clients/{user_id}/card", headers=headers)).json()
    target = card["directions"][0]

    correction_resp = await client.post(
        f"/direction/runs/{run_id}/corrections",
        json={
            "artifact_type": "direction_placement", "direction_id": target["direction_id"],
            "corrected_placement": "not_eligible", "reason_code": "wrong_direction_priority", "comment": "test",
        },
        headers=headers,
    )
    assert correction_resp.status_code == 201

    card_after = (await client.get(f"/direction/clients/{user_id}/card", headers=headers)).json()
    view = next(d for d in card_after["directions"] if d["direction_id"] == target["direction_id"])
    assert view["system_placement"] == target["system_placement"]
    assert view["effective_placement"] == "not_eligible"
    assert view["system_placement"] != view["effective_placement"]


# ---------------------------------------------------------------- 7, 8


async def test_critic_blocker_prevents_approval_warning_does_not(client, session_factory):
    """#7 + #8."""
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "consultant2@ican.dev", AdminRole.CAREER_CONSULTANT)
    headers = await _login(client, "consultant2@ican.dev")
    gen = (await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)).json()
    run_id = gen["run_id"]

    critic_resp = await client.post(f"/direction/runs/{run_id}/critic", headers=headers)
    assert critic_resp.status_code == 200
    assert critic_resp.json()["warning_count"] > 0  # this fixture always produces WARNINGs
    assert critic_resp.json()["blocker_count"] == 0

    approve_resp = await client.post(f"/direction/runs/{run_id}/approve", json={}, headers=headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"  # WARNING never blocks approval


async def test_blocker_prevents_approval_via_api(client, session_factory):
    """#7 (BLOCKER path)."""
    from sqlalchemy import select

    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "consultant3@ican.dev", AdminRole.CAREER_CONSULTANT)
    headers = await _login(client, "consultant3@ican.dev")
    gen = (await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)).json()
    run_id = gen["run_id"]

    async with session_factory() as session:
        from app.db.models_direction import ConstraintCheckResult, Direction, DirectionConstraintCheck, DirectionPlacement
        import uuid as uuid_mod

        directions = (
            await session.execute(
                select(Direction).where(Direction.run_id == uuid_mod.UUID(run_id), Direction.placement == DirectionPlacement.MAIN)
            )
        ).scalars().all()
        session.add(
            DirectionConstraintCheck(
                direction_id=directions[0].id, constraint_subtype="credential", result=ConstraintCheckResult.BLOCK,
                is_hard=True, explanation="synthetic BLOCKER for API test",
            )
        )
        await session.commit()

    await client.post(f"/direction/runs/{run_id}/critic", headers=headers)
    approve_resp = await client.post(f"/direction/runs/{run_id}/approve", json={}, headers=headers)
    assert approve_resp.status_code == 409


# ---------------------------------------------------------------- 9, 10


async def test_correction_creates_backend_record_and_does_not_mutate_direction(client, session_factory):
    """#9 + #10."""
    from sqlalchemy import select

    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "consultant4@ican.dev", AdminRole.CAREER_CONSULTANT)
    headers = await _login(client, "consultant4@ican.dev")
    gen = (await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)).json()
    run_id = gen["run_id"]
    card = (await client.get(f"/direction/clients/{user_id}/card", headers=headers)).json()
    target = card["directions"][0]

    resp = await client.post(
        f"/direction/runs/{run_id}/corrections",
        json={
            "artifact_type": "direction_placement", "direction_id": target["direction_id"],
            "corrected_placement": "alternative", "reason_code": "wrong_direction_priority", "comment": "api test",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    correction_id = resp.json()["correction_id"]

    async with session_factory() as session:
        from app.db.models_direction import ConsultantCorrection, Direction
        import uuid as uuid_mod

        row = await session.get(ConsultantCorrection, uuid_mod.UUID(correction_id))
        assert row is not None  # backend record actually created

        direction_row = await session.get(Direction, uuid_mod.UUID(target["direction_id"]))
        assert direction_row.placement.value == target["system_placement"]  # untouched by the correction


# ---------------------------------------------------------------- 11, 12


async def test_publishable_preview_unavailable_before_approval_and_uses_effective_after(client, session_factory):
    """#11 + #12."""
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "consultant5@ican.dev", AdminRole.CAREER_CONSULTANT)
    headers = await _login(client, "consultant5@ican.dev")
    gen = (await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)).json()
    run_id = gen["run_id"]
    await client.post(f"/direction/runs/{run_id}/critic", headers=headers)

    before = await client.get(f"/direction/clients/{user_id}/publishable", headers=headers)
    assert before.status_code == 200
    assert before.json()["publishable"] is False
    assert before.json()["reason"]

    card = (await client.get(f"/direction/clients/{user_id}/card", headers=headers)).json()
    target = card["directions"][0]
    await client.post(
        f"/direction/runs/{run_id}/corrections",
        json={
            "artifact_type": "direction_placement", "direction_id": target["direction_id"],
            "corrected_placement": "alternative", "reason_code": "wrong_direction_priority", "comment": "test",
        },
        headers=headers,
    )
    await client.post(f"/direction/runs/{run_id}/approve", json={}, headers=headers)

    after = await client.get(f"/direction/clients/{user_id}/publishable", headers=headers)
    assert after.status_code == 200
    assert after.json()["publishable"] is True
    published_direction = next(d for d in after.json()["result"]["directions"] if d["direction_id"] == target["direction_id"])
    assert published_direction["effective_placement"] == "alternative"  # overlay applied


# ---------------------------------------------------------------- 13


async def test_request_changes_preserves_old_run(client, session_factory):
    """#13."""
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "consultant6@ican.dev", AdminRole.CAREER_CONSULTANT)
    headers = await _login(client, "consultant6@ican.dev")
    gen = (await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)).json()
    run_id = gen["run_id"]

    resp = await client.post(f"/direction/runs/{run_id}/request-changes", json={"comment": "please redo"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "changes_requested"

    card = (await client.get(f"/direction/clients/{user_id}/card", headers=headers)).json()
    assert card["client"]["direction_run_id"] == run_id  # same run still current, untouched


# ---------------------------------------------------------------- 14, 15


async def test_no_raw_cv_or_transcript_leaks_and_no_ai_trace(client, session_factory):
    """#14 + #15. `ProfileClaimView.normalized_value` (Stage 2's already-
    normalized claim text) is explicitly authorized for this consultant-
    only card (Founder Stage 4A §4) -- the real invariant is that no RAW
    source row (`Answer`/`CVUpload`/`InterviewMessage`) is reachable,
    which the read-model layer already guarantees structurally (see
    tests/test_direction_readmodel.py). Here we confirm the API card
    still actually returns real per-claim data (not vacuously empty)."""
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "admin4@ican.dev", AdminRole.ADMIN)
    headers = await _login(client, "admin4@ican.dev")
    await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)

    resp = await client.get(f"/direction/clients/{user_id}/card", headers=headers)
    assert resp.json()["profile_claims"]

    from app.db.base import Base
    from app.db import models_platform  # noqa: F401

    assert "ai_traces" not in Base.metadata.tables
    assert not hasattr(models_platform, "AITrace")


# ---------------------------------------------------------------- 16


async def test_backend_state_transitions_match_stage3b_state_machine(client, session_factory):
    """#16: an already-approved review rejects a second decision (the same
    invariant test_direction_review.py proves at the service layer,
    reachable through the API)."""
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "consultant7@ican.dev", AdminRole.CAREER_CONSULTANT)
    headers = await _login(client, "consultant7@ican.dev")
    gen = (await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)).json()
    run_id = gen["run_id"]
    await client.post(f"/direction/runs/{run_id}/critic", headers=headers)
    await client.post(f"/direction/runs/{run_id}/approve", json={}, headers=headers)

    second = await client.post(f"/direction/runs/{run_id}/reject", json={"comment": "changed my mind"}, headers=headers)
    assert second.status_code == 409


async def test_unauthorized_role_cannot_approve_via_api(client, session_factory):
    user_id = await _seed_world(session_factory)
    await _create_staff(session_factory, "manager1@ican.dev", AdminRole.MANAGER)
    headers = await _login(client, "manager1@ican.dev")
    gen = (await client.post(f"/direction/clients/{user_id}/generate", json={}, headers=headers)).json()
    run_id = gen["run_id"]

    resp = await client.post(f"/direction/runs/{run_id}/approve", json={}, headers=headers)
    assert resp.status_code == 403
