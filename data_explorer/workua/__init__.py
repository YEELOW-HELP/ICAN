"""Work.ua Career Guide -- DISCOVERY / REFERENCE layer only.

Work.ua answers one question: *which professions does the largest
Ukrainian job portal currently show its users?* It is a discovery source
for the MNP Career KB -- never a content source. We keep only factual
reference data (profession title, slug, career-guide URL, the fact that
the profession exists); no descriptions, pros/cons, salaries, vacancy
counts or other proprietary editorial text is ever copied.

Nothing in this package writes to the Career KB. It only:
  * crawls the current Career Guide (`inventory.py`),
  * snapshots it to `data_explorer/workua/inventory/*.csv` (reproducible),
  * diffs a fresh crawl against the last snapshot (`refresh.py`).

MNP curation, based on independent occupational knowledge, is what fills
the Career KB (`app/services/career_kb_mnp/catalog_starter.py`).
"""
