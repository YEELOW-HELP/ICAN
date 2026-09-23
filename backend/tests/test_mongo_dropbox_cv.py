"""Dropbox CV upload: provider contract, staff scope and safe document view."""

from datetime import timedelta
from io import BytesIO
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from pydantic import SecretStr

from app.core.config import settings
from app.mongo_runtime import cv_analysis, dropbox_storage, persons
from app.mongo_runtime.core import ADMIN, MANAGER, SUPER_ADMIN, current_staff, database
from app.mongo_runtime.main import app


class Collection:
    def __init__(self, rows=()):
        self.rows = {row["_id"]: dict(row) for row in rows}

    @staticmethod
    def _matches(row, query):
        for key, expected in query.items():
            actual = row.get(key)
            if key == "access_admin_ids":
                if expected not in (actual or []):
                    return False
            elif isinstance(actual, list) and not isinstance(expected, dict):
                if expected not in actual:
                    return False
            elif isinstance(expected, dict) and "$ne" in expected:
                if actual == expected["$ne"]:
                    return False
            elif isinstance(expected, dict) and "$gte" in expected:
                if actual is None or actual < expected["$gte"]:
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query):
        for row in self.rows.values():
            if self._matches(row, query):
                return dict(row)
        return None

    async def find(self, query=None):
        query = query or {}
        for row in self.rows.values():
            if self._matches(row, query):
                yield dict(row)

    async def insert_one(self, row):
        self.rows[row["_id"]] = dict(row)

    async def update_one(self, query, update, upsert=False):
        row = next((row for row in self.rows.values() if self._matches(row, query)), None)
        if row is None:
            if not upsert:
                return SimpleNamespace(matched_count=0)
            row = {key: value for key, value in query.items() if not isinstance(value, dict)}
            row.update(update.get("$setOnInsert", {}))
            self.rows[row["_id"]] = row
        row.update(update.get("$set", {}))
        for key, value in update.get("$addToSet", {}).items():
            row.setdefault(key, [])
            if value not in row[key]:
                row[key].append(value)
        for key, value in update.get("$pull", {}).items():
            row[key] = [item for item in row.get(key, []) if item != value]
        return SimpleNamespace(matched_count=1)

    async def delete_one(self, query):
        key = next((key for key, row in self.rows.items() if self._matches(row, query)), None)
        if key is None:
            return SimpleNamespace(deleted_count=0)
        del self.rows[key]
        return SimpleNamespace(deleted_count=1)

    async def replace_one(self, query, row, upsert=False):
        self.rows[query["_id"]] = dict(row)

    async def count_documents(self, query):
        return sum(self._matches(row, query) for row in self.rows.values())


class Database:
    def __init__(self):
        self.collections = {name: Collection() for name in persons.FACTS.values()}
        self.mnp_persons = Collection([{
            "_id": "person-1", "first_name": "Олена", "status": "active",
            "access_admin_ids": [7],
        }])
        self.mnp_person_documents = Collection()
        self.mnp_file_blobs = Collection()
        self.mnp_cv_analyses = Collection()
        self.mnp_questionnaire_analyses = Collection()
        self.mnp_ai_analysis_events = Collection()
        self.mnp_superadmin_recommendations = Collection()
        self.mnp_employment_stages = Collection()
        self.mnp_client_request_types = Collection()
        self.mnp_person_access = Collection()
        self.admin_users = Collection([{
            "_id": 7, "email": "manager@example.com", "full_name": "Менеджер",
            "role": MANAGER, "is_active": True,
        }])
        self.mnp_skills = Collection([
            {"_id": "skill-1", "canonical_name_uk": "Excel", "status": "active"},
            {"_id": "skill-2", "canonical_name_uk": "Облік у 1С", "status": "active"},
        ])
        self.mnp_skill_aliases = Collection([
            {"_id": "alias-1", "skill_id": "skill-2", "alias": "1С", "status": "active"},
        ])
        self.mnp_careers = Collection()
        self.mnp_career_aliases = Collection()
        self.mnp_career_skill_requirements = Collection()

    def __getitem__(self, name):
        return self.collections[name]



@pytest.mark.asyncio
@pytest.mark.parametrize("selected", [None, "case", "draft", "active", "archived"])
async def test_create_person_status_round_trip(selected):
    db = Database()
    db.mnp_person_access = Collection()
    payload = {"first_name": "Олена"}
    if selected is not None:
        payload["status"] = selected
    manager = {"_id": 7, "role": MANAGER}
    created = await persons.create_person(payload, db, manager)
    expected = selected or "case"
    assert created["core"]["status"] == expected
    assert created["core"]["status_uk"] == persons.STATUS_UK[expected]
    assert db.mnp_persons.rows[created["id"]]["status"] == expected
    loaded = await persons.get_person(created["id"], db, manager)
    assert loaded["core"]["status"] == expected
    assert db.mnp_persons.rows["person-1"]["status"] == "active"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["invalid", "", None, [], {}])
async def test_invalid_person_status_is_rejected_before_writes(invalid):
    db = Database()
    db.mnp_person_access = Collection()
    manager = {"_id": 7, "role": MANAGER}
    with pytest.raises(HTTPException) as create_error:
        await persons.create_person({"first_name": "Олена", "status": invalid}, db, manager)
    assert create_error.value.status_code == 422
    assert len(db.mnp_persons.rows) == 1
    assert not db.mnp_person_access.rows
    with pytest.raises(HTTPException) as update_error:
        await persons.update_person(
            "person-1", {"status": invalid}, db, {"_id": 1, "role": SUPER_ADMIN},
        )
    assert update_error.value.status_code == 422
    assert db.mnp_persons.rows["person-1"]["status"] == "active"


@pytest.mark.asyncio
async def test_status_patch_preserves_scope_and_partial_update():
    db = Database()
    manager = {"_id": 7, "role": MANAGER}
    superadmin = {"_id": 1, "role": SUPER_ADMIN}
    changed = await persons.update_person("person-1", {"status": "case"}, db, superadmin)
    assert changed["core"]["status_uk"] == "КЕЙС"
    assert db.mnp_persons.rows["person-1"]["status_updated_by_staff_id"] == 1
    changed = await persons.update_person("person-1", {"city": "Дніпро"}, db, manager)
    assert changed["core"]["status"] == "case"
    for role in (MANAGER, ADMIN):
        with pytest.raises(HTTPException) as forbidden:
            await persons.update_person("person-1", {"status": "active"}, db, {
                "_id": 7, "role": role,
            })
        assert forbidden.value.status_code == 403
    with pytest.raises(HTTPException) as denied:
        await persons.update_person("person-1", {"city": "Харків"}, db, {"_id": 8, "role": MANAGER})
    assert denied.value.status_code == 404
    assert db.mnp_persons.rows["person-1"]["status"] == "case"


@pytest.mark.asyncio
async def test_dropbox_upload_refreshes_token_and_uses_private_file_id(monkeypatch):
    monkeypatch.setattr(settings, "dropbox_root", "/ican/cv")
    monkeypatch.setattr(settings, "dropbox_app_key", SecretStr("app-key"))
    monkeypatch.setattr(settings, "dropbox_app_secret", SecretStr("app-secret"))
    monkeypatch.setattr(settings, "dropbox_refresh_token", SecretStr("refresh"))
    paths = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/oauth2/token":
            assert b"refresh_token=refresh" in request.content
            return httpx.Response(200, json={"access_token": "short-token"})
        assert request.headers["Authorization"] == "Bearer short-token"
        if request.url.path == "/2/files/create_folder_v2":
            return httpx.Response(409)
        if request.url.path == "/2/files/upload":
            assert json.loads(request.headers["Dropbox-API-Arg"])["path"] == "/ican/cv/person-1_doc-1.pdf"
            assert request.content == b"%PDF-test"
            return httpx.Response(200, json={"id": "id:dropbox-file"})
        if request.url.path == "/2/files/download":
            assert json.loads(request.headers["Dropbox-API-Arg"])["path"] == "id:dropbox-file"
            return httpx.Response(200, content=b"%PDF-test")
        raise AssertionError(request.url.path)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        file_id = await dropbox_storage.upload_cv(
            document_id="doc-1", person_id="person-1", extension="pdf",
            content=b"%PDF-test", client=client,
        )
        assert file_id == "id:dropbox-file"
        assert await dropbox_storage.download_cv(file_id, client=client) == b"%PDF-test"
    assert paths.count("/2/files/create_folder_v2") == 2


@pytest.mark.asyncio
async def test_manager_may_upload_and_download_only_accessible_person(monkeypatch):
    db = Database()
    calls = []

    async def upload(**kwargs):
        calls.append(kwargs)
        return "id:private-cv"

    async def download(file_id):
        assert file_id == "id:private-cv"
        return b"%PDF-saved"

    monkeypatch.setattr(persons.dropbox_storage, "upload_cv", upload)
    monkeypatch.setattr(persons.dropbox_storage, "download_cv", download)
    manager = {"_id": 7, "role": MANAGER}
    other = {"_id": 8, "role": MANAGER}
    filename = "cv.pdf"
    file = UploadFile(filename=filename, file=BytesIO(b"%PDF-saved"))

    with pytest.raises(HTTPException) as denied:
        await persons.admin_upload_cv("person-1", file, db, other)
    assert denied.value.status_code == 404
    assert calls == []

    view = await persons.admin_upload_cv("person-1", file, db, manager)
    assert view["documents"][0]["filename"] == filename
    assert "storage_ref" not in view["documents"][0]
    assert "id:private-cv" not in repr(view)
    document_id = view["documents"][0]["id"]
    assert db.mnp_file_blobs.rows == {}

    with pytest.raises(HTTPException) as denied_download:
        await persons.admin_download_document("person-1", document_id, db, other)
    assert denied_download.value.status_code == 404
    response = await persons.admin_download_document("person-1", document_id, db, manager)
    assert response.body == b"%PDF-saved"
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_invalid_cv_is_rejected_before_dropbox(monkeypatch):
    async def upload(**_kwargs):
        raise AssertionError("invalid file reached Dropbox")

    monkeypatch.setattr(persons.dropbox_storage, "upload_cv", upload)
    db = Database()
    with pytest.raises(HTTPException) as error:
        await persons.admin_upload_cv(
            "person-1", UploadFile(filename="cv.pdf", file=BytesIO(b"not a pdf")),
            db, {"_id": 1, "role": ADMIN},
        )
    assert error.value.status_code == 422
    assert db.mnp_person_documents.rows == {}


@pytest.mark.asyncio
async def test_multipart_api_keeps_scope_and_file_private(monkeypatch):
    db = Database()
    monkeypatch.setattr(settings, "cv_analysis_enabled", True)

    async def upload(**_kwargs):
        return "id:private-cv"

    async def download(_file_id):
        return b"%PDF-saved"

    async def analyze(_db, *, content, filename):
        assert content == b"%PDF-saved" and filename == "cv.pdf"
        return cv_analysis.CvSearchProposal(
            primary_role="Аналітик", alternative_roles=[], skills=[], search_queries=[],
            work_format="", employment_type="", languages=[], summary="",
        ), SimpleNamespace(input_tokens=100, output_tokens=20, trace_id="trace-1")

    monkeypatch.setattr(persons.dropbox_storage, "upload_cv", upload)
    monkeypatch.setattr(persons.dropbox_storage, "download_cv", download)
    monkeypatch.setattr(persons.cv_analysis, "analyze_cv", analyze)
    app.dependency_overrides[database] = lambda: db
    app.dependency_overrides[current_staff] = lambda: {"_id": 7, "role": MANAGER}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/mnp/admin/persons/person-1/documents/cv",
                files={"file": ("cv.pdf", b"%PDF-saved", "application/pdf")},
            )
            assert response.status_code == 201, response.text
            document = response.json()["documents"][0]
            assert "storage_ref" not in document
            file_response = await client.get(
                f"/v1/mnp/admin/persons/person-1/documents/{document['id']}/download"
            )
            assert file_response.status_code == 200
            assert file_response.content == b"%PDF-saved"
            analysis = await client.post(
                f"/v1/mnp/admin/persons/person-1/documents/{document['id']}/analyze",
                json={"permission_confirmed": True},
            )
            assert analysis.status_code == 200, analysis.text
            assert analysis.json()["proposal"]["primary_role"] == "Аналітик"
            app.dependency_overrides[current_staff] = lambda: {"_id": 8, "role": MANAGER}
            denied = await client.get(
                f"/v1/mnp/admin/persons/person-1/documents/{document['id']}/download"
            )
            assert denied.status_code == 404
            denied_analysis = await client.post(
                f"/v1/mnp/admin/persons/person-1/documents/{document['id']}/analyze",
                json={"permission_confirmed": True},
            )
            assert denied_analysis.status_code == 404
    finally:
        app.dependency_overrides.pop(database, None)
        app.dependency_overrides.pop(current_staff, None)


@pytest.mark.asyncio
async def test_ai_extracts_supported_skill_and_matches_taxonomy(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("test-key"))
    monkeypatch.setattr(cv_analysis, "extract_text", lambda *_args: (
        "Досвід роботи\nАналітик даних. Використовував Excel щодня.\n"
            "Навички\nExcel, 1С, SQL\nКонтакт: candidate@example.com"
    ))

    class Gateway:
        async def call_tool(self, **kwargs):
            text = kwargs["messages"][0]["content"]
            assert "candidate@example.com" not in text
            assert "[email]" in text
            return SimpleNamespace(tool_input={
                "primary_role": "Аналітик даних", "alternative_roles": [],
                "skills": [{"name": "Excel", "evidence": "Excel"},
                           {"name": "1С", "evidence": "1С"},
                           {"name": "Python", "evidence": "Python"}],
                "search_queries": ["аналітик даних"], "work_format": "",
                "employment_type": "", "languages": [], "summary": "Досвід аналізу даних",
            }, trace=SimpleNamespace(input_tokens=100, output_tokens=40, trace_id="trace-1"))

    proposal, trace = await cv_analysis.analyze_cv(
        Database(), content=b"unused", filename="cv.pdf", gateway=Gateway(),
    )
    assert proposal.primary_role == "Аналітик даних"
    assert [(s.name, s.canonical_skill_id) for s in proposal.skills] == [
        ("Excel", "skill-1"), ("1С", "skill-2")]
    assert trace.input_tokens == 100


@pytest.mark.asyncio
async def test_analysis_is_cached_and_manager_scope_is_checked_first(monkeypatch):
    monkeypatch.setattr(settings, "cv_analysis_enabled", True)
    db = Database()
    db.mnp_person_documents.rows["doc-1"] = {
        "_id": "doc-1", "person_id": "person-1", "document_type": "cv",
        "filename": "cv.pdf", "sha256": "hash", "storage_provider": "dropbox",
        "storage_ref": "id:private-cv",
    }
    calls = []

    async def download(_file_id):
        return b"%PDF-saved"

    async def analyze(_db, *, content, filename):
        calls.append((content, filename))
        return cv_analysis.CvSearchProposal(
            primary_role="Аналітик", alternative_roles=[], skills=[], search_queries=[],
            work_format="", employment_type="", languages=[], summary="",
        ), SimpleNamespace(input_tokens=100, output_tokens=20, trace_id="trace-1")

    monkeypatch.setattr(persons.dropbox_storage, "download_cv", download)
    monkeypatch.setattr(persons.cv_analysis, "analyze_cv", analyze)
    other = {"_id": 8, "role": MANAGER}
    with pytest.raises(HTTPException) as denied:
        await persons.admin_analyze_cv("person-1", "doc-1", {"permission_confirmed": True}, db, other)
    assert denied.value.status_code == 404
    assert calls == []
    manager = {"_id": 7, "role": MANAGER}
    with pytest.raises(HTTPException) as no_permission:
        await persons.admin_analyze_cv("person-1", "doc-1", {"permission_confirmed": False}, db, manager)
    assert no_permission.value.status_code == 422
    first = await persons.admin_analyze_cv("person-1", "doc-1", {"permission_confirmed": True}, db, manager)
    second = await persons.admin_analyze_cv("person-1", "doc-1", {"permission_confirmed": True}, db, manager)
    assert first["cached"] is False and second["cached"] is True
    assert first["proposal"]["primary_role"] == "Аналітик"
    assert calls == [(b"%PDF-saved", "cv.pdf")]
    assert "storage_ref" not in repr(db.mnp_cv_analyses.rows)


@pytest.mark.asyncio
async def test_missing_ai_key_does_not_send_cv(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", SecretStr(""))
    with pytest.raises(cv_analysis.CvAnalysisError) as error:
        await cv_analysis.analyze_cv(Database(), content=b"%PDF-saved", filename="cv.pdf")
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_questionnaire_analysis_excludes_contacts_and_uses_cache(monkeypatch):
    monkeypatch.setattr(settings, "cv_analysis_enabled", True)
    db = Database()
    db.mnp_persons.rows["person-1"].update({
        "city": "Київ", "phone": "+380671234567", "email": "person@example.com",
        "date_of_birth": "1990-01-01", "notes": "приватна нотатка",
    })
    db.collections["mnp_person_experiences"].rows["exp-1"] = {
        "_id": "exp-1", "person_id": "person-1",
        "raw_job_title": "Бухгалтер", "tools_used": "Excel",
    }
    calls = []

    async def analyze(_db, *, excerpt):
        calls.append(excerpt)
        return cv_analysis.CvSearchProposal(
            primary_role="Бухгалтер", alternative_roles=[], skills=[],
            search_queries=["бухгалтер"], work_format="", employment_type="",
            languages=[], summary="Досвід бухгалтерії",
        ), SimpleNamespace(input_tokens=60, output_tokens=30, trace_id="trace-2")

    monkeypatch.setattr(persons.cv_analysis, "analyze_questionnaire", analyze)
    manager = {"_id": 7, "role": MANAGER}
    other = {"_id": 8, "role": MANAGER}
    with pytest.raises(HTTPException) as denied:
        await persons.admin_analyze_questionnaire(
            "person-1", {"permission_confirmed": True}, db, other)
    assert denied.value.status_code == 404
    first = await persons.admin_analyze_questionnaire(
        "person-1", {"permission_confirmed": True}, db, manager)
    second = await persons.admin_analyze_questionnaire(
        "person-1", {"permission_confirmed": True}, db, manager)
    assert first["cached"] is False and second["cached"] is True
    assert first["proposal"]["primary_role"] == "Бухгалтер"
    assert len(calls) == 1
    assert "Бухгалтер" in calls[0] and "Excel" in calls[0]
    for private in ("+380671234567", "person@example.com", "1990-01-01", "приватна нотатка"):
        assert private not in calls[0]
    monkeypatch.setattr(settings, "cv_analysis_daily_limit", 1)
    db.collections["mnp_person_experiences"].rows["exp-1"]["raw_job_title"] = "Головний бухгалтер"
    with pytest.raises(HTTPException) as limited:
        await persons.admin_analyze_questionnaire(
            "person-1", {"permission_confirmed": True}, db, manager)
    assert limited.value.status_code == 429
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_empty_questionnaire_is_not_sent_to_ai():
    with pytest.raises(cv_analysis.CvAnalysisError) as error:
        await cv_analysis.questionnaire_excerpt(Database(), {
            "core": {"phone": "123", "email": "person@example.com"},
            "experiences": [], "skills": [],
        })
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_cv_analysis_assigns_only_existing_canonical_tags_without_duplicates(monkeypatch):
    monkeypatch.setattr(settings, "cv_analysis_enabled", True)
    db = Database()
    db.mnp_person_documents.rows["doc-1"] = {
        "_id": "doc-1", "person_id": "person-1", "document_type": "cv",
        "filename": "cv.pdf", "sha256": "hash", "storage_provider": "dropbox",
        "storage_ref": "id:private-cv",
    }
    db.collections["mnp_person_skills_v1"].rows["manual-1"] = {
        "_id": "manual-1", "person_id": "person-1", "raw_input": "Word",
        "evidence_state": "self_reported", "source": "admin_manual",
    }

    async def download(_file_id):
        return b"%PDF-saved"

    async def analyze(_db, *, content, filename):
        return cv_analysis.CvSearchProposal(
            primary_role="Аналітик", alternative_roles=[], search_queries=[],
            skills=[
                cv_analysis.ProposedSkill(name="Excel", evidence="Excel", canonical_skill_id="skill-1"),
                cv_analysis.ProposedSkill(name="Python", evidence="Python", canonical_skill_id=None),
                cv_analysis.ProposedSkill(name="Unknown", evidence="Unknown", canonical_skill_id="missing"),
            ], work_format="", employment_type="", languages=[], summary="",
        ), SimpleNamespace(input_tokens=20, output_tokens=10, trace_id="trace-tags")

    monkeypatch.setattr(persons.dropbox_storage, "download_cv", download)
    monkeypatch.setattr(persons.cv_analysis, "analyze_cv", analyze)
    manager = {"_id": 7, "role": MANAGER}
    first = await persons.admin_analyze_cv(
        "person-1", "doc-1", {"permission_confirmed": True}, db, manager)
    second = await persons.admin_analyze_cv(
        "person-1", "doc-1", {"permission_confirmed": True}, db, manager)
    assert first["new_tags_count"] == 1
    assert second["new_tags_count"] == 0
    assert first["detected_tags"] == [{"id": "skill-1", "name": "Excel"}]
    rows = list(db.collections["mnp_person_skills_v1"].rows.values())
    assert len(rows) == 2
    assert rows[0]["evidence_state"] == "self_reported"
    assert rows[1]["canonical_skill_id"] == "skill-1"
    assert rows[1]["evidence_state"] == "system_detected"
    assert rows[1]["supporting_document_id"] == "doc-1"
    assert rows[1]["evidence_excerpt"] == "Excel"
    assert db.mnp_persons.rows["person-1"]["tags"] == [
        {"skill_id": "skill-1", "name": "Excel", "skill_type": None},
    ]


@pytest.mark.asyncio
async def test_analysis_fills_minimum_five_tags_from_matching_career(monkeypatch):
    monkeypatch.setattr(settings, "cv_analysis_enabled", True)
    db = Database()
    db.mnp_skills.rows.update({
        f"skill-{number}": {
            "_id": f"skill-{number}", "canonical_name_uk": name,
            "status": "active", "skill_type": "functional",
        }
        for number, name in ((3, "Фінансовий аналіз"), (4, "Звітність"),
                             (5, "Бюджетування"), (6, "Прогнозування"))
    })
    db.mnp_careers.rows["career-1"] = {
        "_id": "career-1", "canonical_name_uk": "Фінансовий аналітик", "status": "active",
    }
    for number, importance in ((1, "critical"), (3, "high"), (4, "high"),
                               (5, "medium"), (6, "medium")):
        db.mnp_career_skill_requirements.rows[f"rel-{number}"] = {
            "_id": f"rel-{number}", "career_id": "career-1",
            "skill_id": f"skill-{number}", "importance": importance,
            "requirement_type": "must_have", "review_status": "approved",
        }

    result = await persons._assign_analysis_tags(
        db, person_id="person-1", source="questionnaire", source_id="person-1",
        proposal={
            "primary_role": "Фінансовий аналітик", "alternative_roles": [],
            "skills": [{"name": "Excel", "evidence": "Excel",
                        "canonical_skill_id": "skill-1"}],
        },
    )

    assert result["tagging"] == {
        "minimum": 5, "total": 5, "complete": True,
        "career": {"id": "career-1", "name": "Фінансовий аналітик"},
    }
    assert result["new_tags_count"] == 5
    assert len(result["inferred_tags"]) == 4
    assert len(db.mnp_persons.rows["person-1"]["tags"]) == 5
    inferred_rows = [row for row in db.collections["mnp_person_skills_v1"].rows.values()
                     if row.get("evidence_state") == "system_inferred"]
    assert len(inferred_rows) == 4
    assert all(row["inferred_from_career_id"] == "career-1" for row in inferred_rows)


@pytest.mark.asyncio
async def test_questionnaire_detected_tags_do_not_feed_their_own_analysis(monkeypatch):
    monkeypatch.setattr(settings, "cv_analysis_enabled", True)
    db = Database()
    db.collections["mnp_person_experiences"].rows["exp-1"] = {
        "_id": "exp-1", "person_id": "person-1", "raw_job_title": "Аналітик",
        "tools_used": "Excel",
    }
    calls = []

    async def analyze(_db, *, excerpt):
        calls.append(excerpt)
        return cv_analysis.CvSearchProposal(
            primary_role="Аналітик", alternative_roles=[], search_queries=[],
            skills=[cv_analysis.ProposedSkill(
                name="Excel", evidence="Excel", canonical_skill_id="skill-1")],
            work_format="", employment_type="", languages=[], summary="",
        ), SimpleNamespace(input_tokens=20, output_tokens=10, trace_id="trace-tags")

    monkeypatch.setattr(persons.cv_analysis, "analyze_questionnaire", analyze)
    manager = {"_id": 7, "role": MANAGER}
    first = await persons.admin_analyze_questionnaire(
        "person-1", {"permission_confirmed": True}, db, manager)
    second = await persons.admin_analyze_questionnaire(
        "person-1", {"permission_confirmed": True}, db, manager)
    assert first["new_tags_count"] == 1
    assert second["cached"] is True
    assert second["new_tags_count"] == 0
    assert len(calls) == 1
    assert next(iter(db.collections["mnp_person_skills_v1"].rows.values()))["evidence_state"] == "system_detected"


@pytest.mark.asyncio
async def test_ai_recommendations_are_superadmin_only(monkeypatch):
    monkeypatch.setattr(settings, "cv_analysis_enabled", True)
    db = Database()
    for role in (MANAGER, ADMIN):
        staff = {"_id": 7, "role": role}
        with pytest.raises(HTTPException) as get_error:
            await persons.get_ai_recommendations("person-1", db, staff)
        assert get_error.value.status_code == 403
        with pytest.raises(HTTPException) as post_error:
            await persons.generate_ai_recommendations("person-1", db, staff)
        assert post_error.value.status_code == 403
    assert not db.mnp_superadmin_recommendations.rows
    assert not db.mnp_ai_analysis_events.rows


@pytest.mark.asyncio
async def test_superadmin_generates_stores_and_refreshes_private_recommendations(monkeypatch):
    monkeypatch.setattr(settings, "cv_analysis_enabled", True)
    db = Database()
    initial_updated_at = persons.now()
    db.mnp_persons.rows["person-1"]["updated_at"] = initial_updated_at

    async def generate(profile):
        assert profile["id"] == "person-1"
        return persons.ai_recommendations.RecommendationPlan(
            summary="Спочатку уточнити запит і підготувати клієнта до пошуку.",
            steps=[{
                "title": "Уточнити ціль",
                "action": "Провести коротку консультацію та узгодити бажані ролі.",
            }],
            platform_offers=["Індивідуальна кар’єрна консультація"],
            questions_to_clarify=["Який графік роботи підходить?"],
            suggested_workflow_stage="consultation_scheduled",
        ), SimpleNamespace(input_tokens=120, output_tokens=80, trace_id="trace-rec")

    monkeypatch.setattr(persons.ai_recommendations, "generate", generate)
    superadmin = {"_id": 1, "role": SUPER_ADMIN}
    assert await persons.get_ai_recommendations("person-1", db, superadmin) == {
        "recommendation": None,
    }

    created = await persons.generate_ai_recommendations("person-1", db, superadmin)
    assert created["recommendation"]["steps"][0]["title"] == "Уточнити ціль"
    assert created["is_outdated"] is False
    assert created["input_tokens"] == 120
    stored = db.mnp_superadmin_recommendations.rows["person-1"]
    assert stored["generated_by_staff_id"] == 1
    assert stored["profile_updated_at"] == initial_updated_at
    event = next(iter(db.mnp_ai_analysis_events.rows.values()))
    assert event["source"] == "superadmin_recommendations"

    db.mnp_persons.rows["person-1"]["updated_at"] = initial_updated_at + timedelta(seconds=1)
    loaded = await persons.get_ai_recommendations("person-1", db, superadmin)
    assert loaded["is_outdated"] is True
    ordinary_view = await persons.get_person("person-1", db, {"_id": 7, "role": MANAGER})
    assert "ai_recommendations" not in ordinary_view


@pytest.mark.asyncio
async def test_ai_recommendation_context_excludes_direct_identifiers():
    db = Database()
    person = db.mnp_persons.rows["person-1"]
    person.update({
        "phone": "+380501112233", "email": "olena@example.com",
        "telegram_username": "olena_private", "date_of_birth": "1990-01-01",
        "notes": "Передзвонити +380501112233 або написати olena@example.com",
    })
    profile = await persons._person_view(db, person)
    context = persons.ai_recommendations.profile_context(profile)
    assert "Олена" not in context
    assert "+380501112233" not in context
    assert "olena@example.com" not in context
    assert "olena_private" not in context
    assert "1990-01-01" not in context
    assert "[phone]" in context
    assert "[email]" in context


@pytest.mark.asyncio
async def test_ai_recommendations_match_person_tags_to_catalog_careers(monkeypatch):
    monkeypatch.setattr(settings, "cv_analysis_enabled", True)
    db = Database()
    db.mnp_persons.rows["person-1"].update({
        "city": "Харків",
        "tags": [
            {"skill_id": "skill-1", "name": "Excel", "skill_type": "tool"},
            {"skill_id": "skill-2", "name": "Облік у 1С", "skill_type": "tool"},
        ],
    })
    db.mnp_careers.rows["career-accountant"] = {
        "_id": "career-accountant", "canonical_name_uk": "Бухгалтер", "status": "active",
    }
    for number, skill_id in enumerate(("skill-1", "skill-2"), 1):
        db.mnp_career_skill_requirements.rows[f"match-{number}"] = {
            "_id": f"match-{number}", "career_id": "career-accountant",
            "skill_id": skill_id, "importance": "high", "review_status": "approved",
        }

    async def generate(profile):
        assert profile["catalog_career_matches"][0]["name"] == "Бухгалтер"
        return persons.ai_recommendations.RecommendationPlan(
            summary="Можна розпочати пошук бухгалтерських вакансій у Харкові.",
            steps=[{"title": "Пошук вакансій", "action": "Шукати вакансії бухгалтера у Харкові."}],
            platform_offers=["Пошук і підбір вакансій"], questions_to_clarify=[],
            suggested_workflow_stage="in_progress",
        ), SimpleNamespace(input_tokens=80, output_tokens=50, trace_id="trace-career")

    monkeypatch.setattr(persons.ai_recommendations, "generate", generate)
    result = await persons.generate_ai_recommendations(
        "person-1", db, {"_id": 1, "role": SUPER_ADMIN},
    )
    search = result["vacancy_search"]
    assert search["location"] == "Харків"
    assert search["professions"][0] == {
        "career_id": "career-accountant", "name": "Бухгалтер",
        "matched_tags": ["Excel", "Облік у 1С"], "match_count": 2, "score": 6,
    }
    assert search["queries"] == ["Бухгалтер Харків"]
