"""Dropbox CV upload: provider contract, staff scope and safe document view."""

from io import BytesIO
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from pydantic import SecretStr

from app.core.config import settings
from app.mongo_runtime import cv_analysis, dropbox_storage, persons
from app.mongo_runtime.core import ADMIN, MANAGER, current_staff, database
from app.mongo_runtime.main import app


class Collection:
    def __init__(self, rows=()):
        self.rows = {row["_id"]: dict(row) for row in rows}

    async def find_one(self, query):
        for row in self.rows.values():
            if all(row.get(key) == value if key != "access_admin_ids"
                   else value in row.get(key, []) for key, value in query.items()):
                return dict(row)
        return None

    async def find(self, query=None):
        query = query or {}
        for row in self.rows.values():
            if all(row.get(key) == value for key, value in query.items()):
                yield dict(row)

    async def insert_one(self, row):
        self.rows[row["_id"]] = dict(row)

    async def update_one(self, query, update):
        self.rows[query["_id"]].update(update["$set"])

    async def replace_one(self, query, row, upsert=False):
        self.rows[query["_id"]] = dict(row)

    async def count_documents(self, query):
        return sum(
            row.get("person_id") == query["person_id"]
            and row.get("analyzed_at") >= query["analyzed_at"]["$gte"]
            for row in self.rows.values()
        )


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
        self.mnp_skills = Collection([
            {"_id": "skill-1", "canonical_name_uk": "Excel", "status": "active"},
        ])

    def __getitem__(self, name):
        return self.collections[name]


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
        "Навички\nExcel, SQL\nКонтакт: candidate@example.com"
    ))

    class Gateway:
        async def call_tool(self, **kwargs):
            text = kwargs["messages"][0]["content"]
            assert "candidate@example.com" not in text
            assert "[email]" in text
            return SimpleNamespace(tool_input={
                "primary_role": "Аналітик даних", "alternative_roles": [],
                "skills": [{"name": "Excel", "evidence": "Excel"},
                           {"name": "Python", "evidence": "Python"}],
                "search_queries": ["аналітик даних"], "work_format": "",
                "employment_type": "", "languages": [], "summary": "Досвід аналізу даних",
            }, trace=SimpleNamespace(input_tokens=100, output_tokens=40, trace_id="trace-1"))

    proposal, trace = await cv_analysis.analyze_cv(
        Database(), content=b"unused", filename="cv.pdf", gateway=Gateway(),
    )
    assert proposal.primary_role == "Аналітик даних"
    assert [(s.name, s.canonical_skill_id) for s in proposal.skills] == [("Excel", "skill-1")]
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
