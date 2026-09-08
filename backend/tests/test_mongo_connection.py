from contextlib import asynccontextmanager

import pytest
from pydantic import SecretStr
from pymongo.errors import ConfigurationError, OperationFailure

from app.db import mongo
from scripts import check_mongodb


@pytest.mark.asyncio
async def test_client_scope_database_timeouts_and_cleanup(monkeypatch):
    monkeypatch.setattr(mongo.settings, "mongodb_url", SecretStr("mongodb://test.invalid/"))
    monkeypatch.setattr(mongo.settings, "mongodb_database", "ican")
    calls = {}

    class Client:
        def __init__(self, uri, **options):
            calls.update(uri=uri, options=options)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            calls["closed"] = True

        def __getitem__(self, name):
            calls["database"] = name
            return "database-handle"

    monkeypatch.setattr(mongo, "AsyncMongoClient", Client)
    async with mongo.mongo_database() as db:
        assert db == "database-handle"
    assert calls["database"] == "ican"
    assert calls["closed"]
    assert calls["options"]["serverSelectionTimeoutMS"] == 10000
    assert "test.invalid" not in repr(mongo.settings.mongodb_url)


@pytest.mark.asyncio
async def test_missing_url_is_rejected_before_connection(monkeypatch):
    monkeypatch.setattr(mongo.settings, "mongodb_url", SecretStr(""))
    with pytest.raises(ValueError):
        async with mongo.mongo_database():
            pytest.fail("Missing settings must not connect")


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["", "a/b", "a.b", "a b", "$bad", "a\\b"])
async def test_invalid_database_name_is_rejected(monkeypatch, name):
    monkeypatch.setattr(mongo.settings, "mongodb_url", SecretStr("mongodb://test.invalid/"))
    monkeypatch.setattr(mongo.settings, "mongodb_database", name)
    with pytest.raises(ValueError):
        async with mongo.mongo_database():
            pytest.fail("Invalid database must not connect")


@pytest.mark.asyncio
async def test_probe_is_read_only(monkeypatch, capsys):
    calls = []

    class Database:
        name = "ican"

        async def command(self, command):
            calls.append(command)

        async def list_collection_names(self):
            calls.append("list_collection_names")
            return []

    @asynccontextmanager
    async def connection():
        yield Database()

    monkeypatch.setattr(check_mongodb, "mongo_database", connection)
    assert await check_mongodb.check() == 0
    assert calls == ["ping", "list_collection_names"]
    assert "Database: ican" in capsys.readouterr().out


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ConfigurationError("secret-uri"), OperationFailure("secret-uri", 18)])
async def test_probe_does_not_print_driver_exception_secrets(monkeypatch, capsys, error):
    @asynccontextmanager
    async def connection():
        raise error
        yield  # pragma: no cover

    monkeypatch.setattr(check_mongodb, "mongo_database", connection)
    assert await check_mongodb.check() == 1
    assert "secret-uri" not in capsys.readouterr().out
