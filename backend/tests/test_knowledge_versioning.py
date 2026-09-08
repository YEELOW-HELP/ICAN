"""Knowledge Base version lifecycle (brief §14, §25 B/C/D)."""

import pytest

from app.db.models_knowledge import KnowledgeBaseVersionStatus
from app.services.exceptions import (
    KnowledgeBaseVersionNotDraftError,
    KnowledgeBaseVersionNotFoundError,
    NoCurrentKnowledgeBaseVersionError,
)
from app.services.knowledge.versioning import (
    create_draft_version,
    get_current_knowledge_version,
    get_knowledge_version,
    list_knowledge_versions,
    publish_version,
)


async def test_create_draft_version_starts_at_version_1(session_factory):
    async with session_factory() as session:
        draft = await create_draft_version(session)
        assert draft.version == 1
        assert draft.status == KnowledgeBaseVersionStatus.DRAFT
        assert draft.is_current is False


async def test_no_current_version_before_anything_is_published(session_factory):
    async with session_factory() as session:
        await create_draft_version(session)
        with pytest.raises(NoCurrentKnowledgeBaseVersionError):
            await get_current_knowledge_version(session)


async def test_publish_makes_version_current(session_factory):
    async with session_factory() as session:
        draft = await create_draft_version(session)
        published = await publish_version(session, draft.id)

        assert published.status == KnowledgeBaseVersionStatus.PUBLISHED
        assert published.is_current is True
        assert published.published_at is not None

        current = await get_current_knowledge_version(session)
        assert current.id == published.id


async def test_publishing_a_new_version_supersedes_the_previous_one(session_factory):
    async with session_factory() as session:
        v1 = await publish_version(session, (await create_draft_version(session)).id)
        v2 = await publish_version(session, (await create_draft_version(session)).id)

        current = await get_current_knowledge_version(session)
        assert current.id == v2.id

        v1_reloaded = await get_knowledge_version(session, v1.id)
        assert v1_reloaded.status == KnowledgeBaseVersionStatus.SUPERSEDED
        assert v1_reloaded.is_current is False


async def test_superseded_version_remains_queryable(session_factory):
    async with session_factory() as session:
        v1 = await publish_version(session, (await create_draft_version(session)).id)
        await publish_version(session, (await create_draft_version(session)).id)

        versions = await list_knowledge_versions(session)
        assert v1.id in {v.id for v in versions}


async def test_cannot_publish_an_already_published_version_twice(session_factory):
    async with session_factory() as session:
        v1 = await publish_version(session, (await create_draft_version(session)).id)
        with pytest.raises(KnowledgeBaseVersionNotDraftError):
            await publish_version(session, v1.id)


async def test_version_numbers_increment_monotonically(session_factory):
    async with session_factory() as session:
        v1 = await create_draft_version(session)
        v2 = await create_draft_version(session)
        assert v2.version == v1.version + 1


async def test_getting_nonexistent_version_raises_not_found(session_factory):
    import uuid

    async with session_factory() as session:
        with pytest.raises(KnowledgeBaseVersionNotFoundError):
            await get_knowledge_version(session, uuid.uuid4())
