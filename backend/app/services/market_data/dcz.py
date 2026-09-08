"""State Employment Service (DCZ) open-data market snapshots.

The source XML is large (currently over 120 MB), so it is parsed as a stream.
Only exact, deterministic Career KB aliases are accepted: an unknown job title
is counted as unmatched and never creates a new career or a fabricated mapping.
"""

from __future__ import annotations

import asyncio
import re
import statistics
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import AsyncIterator, Iterable

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models_career_kb_mnp import (
    CareerLifecycleStatus,
    MnpCareer,
    MnpMarketSnapshot,
    MnpSalarySnapshot,
)

DATASET_ID = "a95174b2-ff4b-43f8-bee2-a89d3a258215"
DATASET_PAGE = f"https://data.gov.ua/dataset/{DATASET_ID}"
CKAN_PACKAGE_URL = f"https://data.gov.ua/api/3/action/package_show?id={DATASET_ID}"
SOURCE = "data.gov.ua/dcz"
QUALITY = "OFFICIAL_OPEN_DATA"

_CDATA_RE = re.compile(r"^!?\[CDATA\[(.*)\]\]$", re.DOTALL)
_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^0-9a-zа-яіїєґ]+", re.IGNORECASE)
_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_SALARY_RE = re.compile(r"(\d[\d\s\u00a0]*)")
_REGION_RE = re.compile(r"^([^,]*?\sобласть)(?:,|$)", re.IGNORECASE)
_refresh_lock = asyncio.Lock()


@dataclass(frozen=True)
class Resource:
    id: str
    name: str
    url: str
    snapshot_date: date


@dataclass(frozen=True)
class Vacancy:
    title: str
    region: str | None
    salary: int | None


@dataclass
class Metric:
    count: int = 0
    salaries: list[int] = field(default_factory=list)

    def add(self, salary: int | None) -> None:
        self.count += 1
        if salary is not None and 1_000 <= salary <= 1_000_000:
            self.salaries.append(salary)


def clean_xml_text(value: str | None) -> str:
    text = (value or "").strip()
    match = _CDATA_RE.match(text)
    if match:
        text = match.group(1)
    return _SPACE_RE.sub(" ", text).strip()


def normalize_title(value: str) -> str:
    return _SPACE_RE.sub(" ", _PUNCT_RE.sub(" ", value.casefold())).strip()


def normalize_region(value: str | None) -> str | None:
    raw = clean_xml_text(value)
    if not raw:
        return None
    match = _REGION_RE.match(raw)
    if match:
        return match.group(1).strip()
    lowered = raw.casefold()
    if "київ" in lowered and "київська область" not in lowered:
        return "м. Київ"
    if "автономна республіка крим" in lowered:
        return "Автономна Республіка Крим"
    return raw.split(",", 1)[0].strip() or None


def parse_salary(value: str | None) -> int | None:
    match = _SALARY_RE.search(clean_xml_text(value))
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def parse_job_element(element: ET.Element) -> Vacancy | None:
    values = {child.tag.rsplit("}", 1)[-1].lower(): child.text for child in element}
    title = clean_xml_text(values.get("name"))
    if not title:
        return None
    return Vacancy(
        title=title,
        region=normalize_region(values.get("region")),
        salary=parse_salary(values.get("salary")),
    )


async def iter_vacancies(chunks: AsyncIterator[bytes]) -> AsyncIterator[Vacancy]:
    parser = ET.XMLPullParser(events=("end",))
    async for chunk in chunks:
        parser.feed(chunk)
        for _event, element in parser.read_events():
            if element.tag.rsplit("}", 1)[-1].lower() == "job":
                vacancy = parse_job_element(element)
                element.clear()
                if vacancy is not None:
                    yield vacancy


def _resource_date(item: dict) -> date | None:
    name_match = _DATE_RE.search(str(item.get("name", "")))
    if name_match:
        day, month, year = map(int, name_match.groups())
        return date(year, month, day)
    value = item.get("last_modified") or item.get("created")
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


async def latest_resource(client: httpx.AsyncClient) -> Resource:
    response = await client.get(CKAN_PACKAGE_URL)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError("Data.gov.ua did not return a successful CKAN response")
    candidates: list[tuple[date, dict]] = []
    for item in payload.get("result", {}).get("resources", []):
        resource_date = _resource_date(item)
        if resource_date and str(item.get("format", "")).upper() == "XML" and item.get("url"):
            candidates.append((resource_date, item))
    if not candidates:
        raise RuntimeError("No XML resource found in the DCZ dataset")
    snapshot_date, item = max(candidates, key=lambda row: (row[0], str(row[1].get("created", ""))))
    # `mnp_market_snapshots.source_version` is String(32); a UUID without
    # hyphens stays unique while fitting the established schema exactly.
    version = str(item["id"]).replace("-", "")[:32]
    return Resource(id=version, name=str(item.get("name", "")), url=str(item["url"]), snapshot_date=snapshot_date)


async def career_lookup(session: AsyncSession) -> dict[str, MnpCareer]:
    result = await session.execute(
        select(MnpCareer)
        .options(selectinload(MnpCareer.aliases))
        .where(MnpCareer.status != CareerLifecycleStatus.ARCHIVED)
    )
    lookup: dict[str, MnpCareer] = {}
    ambiguous: set[str] = set()
    for career in result.scalars().unique().all():
        names = [career.canonical_name_uk, career.canonical_name_en, *(alias.alias for alias in career.aliases)]
        for name in names:
            key = normalize_title(name)
            if not key:
                continue
            existing = lookup.get(key)
            if existing is not None and existing.id != career.id:
                ambiguous.add(key)
            else:
                lookup[key] = career
    for key in ambiguous:
        lookup.pop(key, None)
    return lookup


def _percentile(values: list[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return float(ordered[index])


def _trend(current: int, previous: int | None) -> str | None:
    if not previous:
        return None
    ratio = current / previous
    if ratio > 1.1:
        return "up"
    if ratio < 0.9:
        return "down"
    return "flat"


async def _existing_version_count(session: AsyncSession, version: str) -> int:
    return int((await session.scalar(
        select(func.count(MnpMarketSnapshot.id)).where(
            MnpMarketSnapshot.source == SOURCE,
            MnpMarketSnapshot.source_version == version,
        )
    )) or 0)


async def refresh_market_data(
    session: AsyncSession,
    *,
    client: httpx.AsyncClient | None = None,
    force: bool = False,
) -> dict:
    """Download the latest DCZ resource and atomically replace that snapshot."""

    async with _refresh_lock:
        owns_client = client is None
        http = client or httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=30.0), follow_redirects=True)
        try:
            resource = await latest_resource(http)
            existing = await _existing_version_count(session, resource.id)
            if existing and not force:
                return {
                    "status": "unchanged", "snapshot_date": resource.snapshot_date.isoformat(),
                    "source_version": resource.id, "snapshots": existing,
                }

            lookup = await career_lookup(session)
            metrics: dict[tuple[object, str | None], Metric] = defaultdict(Metric)
            parsed = matched = 0
            async with http.stream("GET", resource.url) as response:
                response.raise_for_status()
                async for vacancy in iter_vacancies(response.aiter_bytes(chunk_size=128 * 1024)):
                    parsed += 1
                    career = lookup.get(normalize_title(vacancy.title))
                    if career is None:
                        continue
                    matched += 1
                    metrics[(career.id, None)].add(vacancy.salary)
                    if vacancy.region:
                        metrics[(career.id, vacancy.region)].add(vacancy.salary)

            previous_result = await session.execute(
                select(MnpMarketSnapshot)
                .where(MnpMarketSnapshot.source == SOURCE, MnpMarketSnapshot.snapshot_date < resource.snapshot_date)
                .order_by(MnpMarketSnapshot.snapshot_date.desc())
            )
            previous: dict[tuple[object, str | None], int] = {}
            for row in previous_result.scalars().all():
                previous.setdefault((row.career_id, row.region), row.vacancy_count or 0)

            old_ids = list((await session.scalars(
                select(MnpMarketSnapshot.id).where(
                    MnpMarketSnapshot.source == SOURCE,
                    MnpMarketSnapshot.source_version == resource.id,
                )
            )).all())
            if old_ids:
                await session.execute(delete(MnpSalarySnapshot).where(MnpSalarySnapshot.market_snapshot_id.in_(old_ids)))
                await session.execute(delete(MnpMarketSnapshot).where(MnpMarketSnapshot.id.in_(old_ids)))

            snapshots: list[tuple[MnpMarketSnapshot, Metric]] = []
            for (career_id, region), metric in metrics.items():
                snapshot = MnpMarketSnapshot(
                    career_id=career_id,
                    country="UA",
                    region=region,
                    snapshot_date=resource.snapshot_date,
                    source=SOURCE,
                    source_version=resource.id,
                    data_quality=QUALITY,
                    sample_size=metric.count,
                    vacancy_count=metric.count,
                    demand_trend=_trend(metric.count, previous.get((career_id, region))),
                )
                session.add(snapshot)
                snapshots.append((snapshot, metric))
            await session.flush()
            for snapshot, metric in snapshots:
                if metric.salaries:
                    session.add(MnpSalarySnapshot(
                        market_snapshot_id=snapshot.id,
                        currency="UAH",
                        period="month",
                        percentile_25=_percentile(metric.salaries, .25),
                        median=float(statistics.median(metric.salaries)),
                        percentile_75=_percentile(metric.salaries, .75),
                    ))
            matched_career_ids = {career_id for career_id, _region in metrics}
            if matched_career_ids:
                careers = await session.scalars(select(MnpCareer).where(MnpCareer.id.in_(matched_career_ids)))
                for career in careers:
                    career.market_data_limited = False
            await session.commit()
            return {
                "status": "updated",
                "snapshot_date": resource.snapshot_date.isoformat(),
                "source_version": resource.id,
                "parsed_vacancies": parsed,
                "matched_vacancies": matched,
                "unmatched_vacancies": parsed - matched,
                "snapshots": len(snapshots),
            }
        except Exception:
            await session.rollback()
            raise
        finally:
            if owns_client:
                await http.aclose()


async def refresh_if_changed(session: AsyncSession) -> dict:
    """Cheap CKAN metadata check; downloads 120+ MB only for a new version."""
    return await refresh_market_data(session, force=False)
