"""Crawl + snapshot the Work.ua Career Guide profession list.

Only titles / slugs / career-guide URLs are extracted -- the reference
facts §1 of the Founder brief explicitly permits. No description text is
read or stored.
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CAREER_GUIDE_URL = "https://www.work.ua/career-guide/"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

INVENTORY_DIR = Path(__file__).resolve().parent / "inventory"

# One profession card on a Career Guide page:
#   <span id="SLUG"></span>
#   <div class="card ... profession-list ...">
#     ... <h2 ...><a href="SLUG/">Title</a></h2>
_CARD_RE = re.compile(
    r'<span id="([a-z0-9][a-z0-9-]*)"></span>\s*'
    r'<div class="card[^"]*profession-list[^"]*">'
    r'.*?<h2[^>]*><a href="([^"]+)">(.*?)</a>',
    re.S,
)
_PAGE_LINK_RE = re.compile(r'href="/career-guide/\?page=(\d+)"')


@dataclass(frozen=True)
class WorkuaProfession:
    title_uk: str
    slug: str
    url: str
    page: int


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        return resp.read().decode("utf-8", errors="replace")


def parse_page(html_text: str, page: int) -> list[WorkuaProfession]:
    out: list[WorkuaProfession] = []
    for m in _CARD_RE.finditer(html_text):
        slug_span, href, raw_title = m.group(1), m.group(2), m.group(3)
        title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
        slug = href.strip("/").split("/")[-1]
        if not title or slug != slug_span:
            continue
        out.append(WorkuaProfession(
            title_uk=title, slug=slug, url=f"https://www.work.ua/career-guide/{slug}/", page=page,
        ))
    return out


def page_count(html_text: str) -> int:
    return max((int(n) for n in _PAGE_LINK_RE.findall(html_text)), default=1)


def crawl(*, fetch=_fetch) -> list[WorkuaProfession]:
    """Walk every Career Guide page. Deduplicated, deterministic order."""
    first = fetch(CAREER_GUIDE_URL)
    total_pages = page_count(first)
    by_slug: dict[str, WorkuaProfession] = {}
    for p in parse_page(first, 1):
        by_slug.setdefault(p.slug, p)
    for page in range(2, total_pages + 1):
        for p in parse_page(fetch(f"{CAREER_GUIDE_URL}?page={page}"), page):
            by_slug.setdefault(p.slug, p)
    professions = sorted(by_slug.values(), key=lambda x: (x.page, x.slug))
    _validate(professions)
    return professions


def _validate(professions: list[WorkuaProfession]) -> None:
    slugs = [p.slug for p in professions]
    urls = [p.url for p in professions]
    assert len(slugs) == len(set(slugs)), "duplicate slug in inventory"
    assert len(urls) == len(set(urls)), "duplicate url in inventory"
    assert all(p.title_uk.strip() for p in professions), "empty profession title"


# --- snapshot io -----------------------------------------------------------
_HEADER = ["workua_title_uk", "workua_slug", "workua_url", "page", "discovered_at"]


def snapshot_path(date: str | None = None) -> Path:
    date = date or dt.date.today().isoformat()
    return INVENTORY_DIR / f"workua_career_inventory_{date}.csv"


def write_snapshot(professions: list[WorkuaProfession], *, date: str | None = None) -> Path:
    date = date or dt.date.today().isoformat()
    path = snapshot_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(_HEADER)
        for p in professions:
            w.writerow([p.title_uk, p.slug, p.url, p.page, date])
    return path


def load_snapshot(path: Path) -> list[WorkuaProfession]:
    with path.open(encoding="utf-8") as f:
        return [
            WorkuaProfession(r["workua_title_uk"], r["workua_slug"], r["workua_url"], int(r["page"]))
            for r in csv.DictReader(f)
        ]


def latest_snapshot() -> Path | None:
    if not INVENTORY_DIR.is_dir():
        return None
    snaps = sorted(INVENTORY_DIR.glob("workua_career_inventory_*.csv"))
    return snaps[-1] if snaps else None
