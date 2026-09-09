from __future__ import annotations

from io import BytesIO
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from app.mongo_runtime.core import Database

router = APIRouter(prefix="/v1/mnp")
SOURCE_NAME = "Державна служба зайнятості України"
SOURCE_URL = "https://data.gov.ua"


async def latest_date(db):
    row = await db.mnp_market_snapshots.find_one(sort=[("snapshot_date", -1)])
    return row.get("snapshot_date") if row else None


async def joined(db, snapshot):
    career = await db.mnp_careers.find_one({"_id": snapshot.get("career_id")}) or {}
    family = await db.mnp_career_families.find_one({"_id": career.get("career_family_id")}) or {}
    salary = await db.mnp_salary_snapshots.find_one({"market_snapshot_id": snapshot["_id"]}) or {}
    return career, family, salary


@router.get("/market/overview")
async def overview(db: Database, region: str | None = Query(default=None, max_length=128),
                   limit: int = Query(default=12, ge=1, le=30)):
    latest = await latest_date(db)
    if latest is None:
        return {"available": False, "message": "Ринкові дані ще не синхронізовано",
                "source": SOURCE_NAME, "source_url": SOURCE_URL, "regions": [],
                "region_summaries": [], "items": []}
    names = await db.mnp_market_snapshots.distinct("region", {"snapshot_date": latest, "region": {"$ne": None}})
    regions = sorted(x for x in names if x)
    selected = region if region in regions else None
    query = {"snapshot_date": latest, "region": selected}
    items = []
    async for snapshot in db.mnp_market_snapshots.find(query).sort("vacancy_count", -1).limit(limit):
        career, family, salary = await joined(db, snapshot)
        items.append({"career_id": str(career.get("_id", "")), "career_code": career.get("code"),
                      "name": career.get("canonical_name_uk"), "family": family.get("name_uk"),
                      "vacancy_count": snapshot.get("vacancy_count", 0), "trend": snapshot.get("demand_trend"),
                      "salary_median": salary.get("median"), "salary_p25": salary.get("percentile_25"),
                      "salary_p75": salary.get("percentile_75")})
    summaries = []
    pipeline = [{"$match": {"snapshot_date": latest, "region": {"$ne": None}}},
                {"$group": {"_id": "$region", "vacancy_count": {"$sum": "$vacancy_count"}}},
                {"$sort": {"_id": 1}}]
    cursor = await db.mnp_market_snapshots.aggregate(pipeline)
    async for row in cursor:
        summaries.append({"region": row["_id"], "vacancy_count": int(row["vacancy_count"] or 0),
                          "salary_average": None})
    total = 0
    async for row in db.mnp_market_snapshots.find(query, {"vacancy_count": 1}):
        total += int(row.get("vacancy_count") or 0)
    return {"available": True, "snapshot_date": str(latest), "selected_region": selected,
            "total_vacancies": total, "source": SOURCE_NAME, "source_url": SOURCE_URL,
            "methodology_note": "Агреговані офіційні дані, зіставлені з Career KB ICAN.",
            "regions": regions, "region_summaries": summaries, "items": items}


@router.get("/market/export.xlsx")
async def export_market(db: Database):
    latest = await latest_date(db)
    if latest is None:
        raise HTTPException(404, "Ринкові дані ще не синхронізовано")
    workbook = Workbook(); sheet = workbook.active; sheet.title = "Усі дані"
    sheet.append(["Дата зрізу", "Регіон", "Код професії", "Професія", "Категорія",
                  "Кількість вакансій", "Медіанна зарплата", "Валюта", "Джерело"])
    careers = {str(row["_id"]): row async for row in db.mnp_careers.find()}
    families = {str(row["_id"]): row async for row in db.mnp_career_families.find()}
    salaries = {str(row["market_snapshot_id"]): row async for row in db.mnp_salary_snapshots.find()}
    async for snapshot in db.mnp_market_snapshots.find({"snapshot_date": latest}).sort([("region", 1), ("vacancy_count", -1)]):
        career = careers.get(str(snapshot.get("career_id")), {})
        family = families.get(str(career.get("career_family_id")), {})
        salary = salaries.get(str(snapshot["_id"]), {})
        sheet.append([str(latest), snapshot.get("region") or "Уся Україна", career.get("code"),
                      career.get("canonical_name_uk"), family.get("name_uk"), snapshot.get("vacancy_count"),
                      salary.get("median"), salary.get("currency"), snapshot.get("source")])
    sheet.freeze_panes = "A2"; sheet.auto_filter.ref = sheet.dimensions
    output = BytesIO(); workbook.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="ican-market-{latest}.xlsx"'})
