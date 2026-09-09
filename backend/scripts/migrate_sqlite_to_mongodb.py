"""One-time, repeatable copy of every ICAN SQLite table into MongoDB.

No source row is deleted. Existing Mongo collections are left untouched unless
--replace is explicitly supplied.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

from pymongo import AsyncMongoClient
from pymongo.server_api import ServerApi

from app.core.config import settings

DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "data" / "dev" / "mnp_dev.sqlite"


ENUM_COLUMNS = {
    "role", "status", "source", "education_level", "credential_type", "evidence_state",
    "is_current", "custom_status", "proficiency", "level", "activity_type", "document_type",
    "work_format", "has_driver_license", "has_car", "willing_to_relocate", "demand_trend",
    "data_quality", "review_status", "skill_type", "requirement_type", "relation_type",
    "entry_mode", "source_mode", "goal_type", "ranking_mode", "route_type",
}


def normalize(key, value):
    if key in {"is_active", "is_creator", "bootstrap_owner"} and value is not None:
        return bool(value)
    if key in ENUM_COLUMNS and isinstance(value, str):
        value = value.lower()
    if isinstance(value, bytes):
        return value
    if isinstance(value, str) and value[:1] in "[{":
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
    return value


def read_database(path: Path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    tables = [row[0] for row in connection.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"
    )]
    result = {}
    for table in tables:
        rows = []
        for raw in connection.execute(f'SELECT * FROM "{table}"'):
            row = {key: normalize(key, raw[key]) for key in raw.keys()}
            if "id" in row:
                row["_id"] = row.pop("id")
            elif table == "mnp_person_access":
                row["_id"] = f"{row['person_id']}:{row['admin_id']}"
            else:
                row["_id"] = f"{table}:{len(rows) + 1}"
            rows.append(row)
        result[table] = rows
    connection.close()
    return result


async def migrate(source: Path, replace: bool):
    url = settings.mongodb_url.get_secret_value()
    if not url:
        raise SystemExit("MONGODB_URL is not configured")
    if not source.exists():
        raise SystemExit(f"SQLite source not found: {source}")
    tables = read_database(source)
    client = AsyncMongoClient(url, server_api=ServerApi("1"), serverSelectionTimeoutMS=10000)
    db = client[settings.mongodb_database]
    await client.admin.command("ping")
    for name, rows in tables.items():
        collection = db[name]
        existing = await collection.estimated_document_count()
        if existing and not replace:
            print(f"SKIP {name}: MongoDB already contains {existing}")
            continue
        if replace:
            await collection.delete_many({})
        if rows:
            await collection.insert_many(rows, ordered=False)
        print(f"OK   {name}: {len(rows)}")
    # Materialized access array keeps manager list queries fast.
    async for grant in db.mnp_person_access.find({}, {"person_id": 1, "admin_id": 1}):
        await db.mnp_persons.update_one({"_id": grant["person_id"]},
                                        {"$addToSet": {"access_admin_ids": grant["admin_id"]}})
    await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--replace", action="store_true", help="replace matching MongoDB collections")
    args = parser.parse_args()
    asyncio.run(migrate(args.source, args.replace))
