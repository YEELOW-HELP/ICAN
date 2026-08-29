"""O*NET bulk-database import pipeline (Matching V1 M4.6 — "Career Vector
Data: Production O*NET Import").

Offline, deterministic, zero-AI. Nothing in this package imports
`app.ai_gateway` or any AI service, and nothing here is imported by the
application runtime (`app/`). It exists to turn the official O*NET bulk
text-database releases into:

  1. a full local reference DB  — data/onet/onet_reference.sqlite  (all
     ~1000 O*NET-SOC occupations, every scale the 4 Matching V1 vector
     families need) — GITIGNORED, rebuilt from the scripts;
  2. a scoped, committed source artifact — app/services/career_kb/
     onet_source_v3.json — one record per O*NET-SOC code that a
     CareerExternalMapping actually points at, which the offline
     `career_kb` seed (`seed_v3.py`) consumes. This keeps CI network-free
     (Founder Review "M3" §18).

Run order:
    python -m scripts.onet_import.download_onet
    python -m scripts.onet_import.build_onet_reference
    python -m scripts.onet_import.export_source_artifact
    python -m scripts.onet_import.suggest_crosswalk

Licensing: the O*NET database content is licensed CC BY 4.0, attributed to
the O*NET Database, U.S. Department of Labor, Employment and Training
Administration, National Center for O*NET Development. See
docs/engineering/27_MATCHING_V1_M4_6_ONET_PRODUCTION_IMPORT.md.
"""
