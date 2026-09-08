"""Explicit MongoDB connection for the incremental storage migration.

This module does not replace the SQLAlchemy session or mirror data to MongoDB.
Clients are created inside their event loop and always closed by the caller.
Never include driver exception text in logs: it may contain connection details.
"""
from contextlib import asynccontextmanager

from pymongo import AsyncMongoClient

from app.core.config import settings


@asynccontextmanager
async def mongo_database():
    uri = settings.mongodb_url.get_secret_value()
    if not uri:
        raise ValueError("MONGODB_URL is not configured")
    database_name = settings.mongodb_database
    if not database_name or any(c in database_name for c in '/\\. "$\x00'):
        raise ValueError("MONGODB_DATABASE is invalid")
    async with AsyncMongoClient(
        uri,
        appname="ICAN",
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
        timeoutMS=15000,
        tz_aware=True,
        uuidRepresentation="standard",
    ) as client:
        yield client[database_name]
