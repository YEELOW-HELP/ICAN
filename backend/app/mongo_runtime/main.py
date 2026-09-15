from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pymongo import AsyncMongoClient
from pymongo.server_api import ServerApi

from app.core.config import settings
from app.core.paths import FRONTEND_ROOT
from app.mongo_runtime.auth import router as auth_router
from app.mongo_runtime.careers import router as careers_router
from app.mongo_runtime.market import router as market_router
from app.mongo_runtime.persons import router as persons_router


async def ensure_indexes(db) -> None:
    await db.admin_users.create_index("email", unique=True)
    await db.admin_users.create_index("bootstrap_owner", unique=True, sparse=True)
    await db.mnp_web_sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.mnp_web_sessions.create_index("token_hash", unique=True, sparse=True)
    await db.mnp_persons.create_index(
        "identity_user_id", unique=True,
        partialFilterExpression={"identity_user_id": {"$type": "string"}},
    )
    await db.mnp_persons.create_index("access_admin_ids")
    await db.mnp_person_access.create_index([("person_id", 1), ("admin_id", 1)], unique=True)
    await db.mnp_cv_analyses.create_index([("person_id", 1), ("analyzed_at", -1)])
    await db.mnp_questionnaire_analyses.create_index([("person_id", 1), ("analyzed_at", -1)])
    await db.mnp_ai_analysis_events.create_index([("person_id", 1), ("analyzed_at", -1)])
    await db.mnp_careers.create_index("code", unique=True)
    await db.mnp_market_snapshots.create_index([("snapshot_date", -1), ("region", 1)])
    highest_staff = await db.admin_users.find_one(sort=[("_id", -1)])
    if highest_staff:
        await db.counters.update_one({"_id": "admin_users"},
                                     {"$max": {"value": int(highest_staff["_id"])}}, upsert=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = settings.mongodb_url.get_secret_value()
    if not url:
        raise RuntimeError("MONGODB_URL is required; PostgreSQL fallback is intentionally disabled")
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is required")
    client = AsyncMongoClient(url, server_api=ServerApi("1"), serverSelectionTimeoutMS=10000)
    await client.admin.command("ping")
    app.state.mongo_client = client
    app.state.database = client[settings.mongodb_database]
    await ensure_indexes(app.state.database)
    try:
        yield
    finally:
        await client.close()


app = FastAPI(title="ICAN MongoDB API", lifespan=lifespan)
cors_origins = [origin.strip().rstrip("/") for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=cors_origins,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(persons_router)
app.include_router(careers_router)
app.include_router(market_router)


@app.get("/health")
async def health():
    await app.state.database.command("ping")
    return {"status": "ok", "storage": "mongodb", "database": settings.mongodb_database}


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/mnp/")


frontend = FRONTEND_ROOT / "dist"
if frontend.is_dir():
    app.mount("/mnp", StaticFiles(directory=frontend, html=True), name="mnp")
