"""Work.ua Career Guide discovery layer -- offline tests.

No network: `parse_page` is tested against a minimal HTML fixture, and
`refresh.run` against a fake fetch that replays fixture pages.
"""

from __future__ import annotations

from data_explorer.workua import inventory as inv
from data_explorer.workua import refresh

_PAGE_TMPL = """
<html><body>
<a href="/career-guide/?page=2">2</a><a href="/career-guide/?page=3">3</a>
{cards}
</body></html>
"""
_CARD = (
    '<span id="{slug}"></span>'
    '<div class="card card-hover profession-list mt-lg">'
    '<div class="row"><div class="col"><h2 class="mt-lg"><a href="{slug}/">{title}</a></h2>'
    '<p>ignored prose</p></div></div></div>'
)


def _page(*cards):
    return _PAGE_TMPL.format(cards="".join(_CARD.format(slug=s, title=t) for s, t in cards))


def test_parse_page_extracts_title_slug_url_only():
    html = _page(("accountant", "Бухгалтер"), ("nurse", "Медсестра"))
    rows = inv.parse_page(html, page=1)
    assert [(r.slug, r.title_uk) for r in rows] == [("accountant", "Бухгалтер"), ("nurse", "Медсестра")]
    assert rows[0].url == "https://www.work.ua/career-guide/accountant/"
    assert inv.page_count(html) == 3


def test_crawl_walks_all_pages_and_dedupes():
    pages = {
        inv.CAREER_GUIDE_URL: _page(("a", "Альфа"), ("b", "Бета")),
        f"{inv.CAREER_GUIDE_URL}?page=2": _page(("b", "Бета"), ("c", "Гама")),
        f"{inv.CAREER_GUIDE_URL}?page=3": _page(("d", "Дельта")),
    }
    got = inv.crawl(fetch=lambda url: pages[url])
    assert sorted(p.slug for p in got) == ["a", "b", "c", "d"]


def test_refresh_diffs_against_previous_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(inv, "INVENTORY_DIR", tmp_path)
    monkeypatch.setattr(refresh.inv, "INVENTORY_DIR", tmp_path)

    v1 = {
        inv.CAREER_GUIDE_URL: _page(("a", "Альфа"), ("b", "Бета")),
        f"{inv.CAREER_GUIDE_URL}?page=2": _page(),
        f"{inv.CAREER_GUIDE_URL}?page=3": _page(),
    }
    d1 = refresh.run(fetch=lambda u: v1[u])
    assert d1.current_count == 2 and d1.previous_date is None

    v2 = {
        inv.CAREER_GUIDE_URL: _page(("a", "Альфа"), ("c", "Гама")),
        f"{inv.CAREER_GUIDE_URL}?page=2": _page(),
        f"{inv.CAREER_GUIDE_URL}?page=3": _page(),
    }
    d2 = refresh.run(fetch=lambda u: v2[u])
    assert {p.slug for p in d2.new} == {"c"}
    assert {p.slug for p in d2.removed} == {"b"}
    assert {p.slug for p in d2.unchanged} == {"a"}
    assert "changed nothing in the Career KB" in d2.as_report()
