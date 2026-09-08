"""Aggregator: importing this module runs every per-family block, each of
which registers its careers via `_c(...)` in catalog_data.STARTER_CAREERS.

Modules are imported one by one; a not-yet-written module is skipped so
the catalog can be built incrementally during development. All 12 must
exist for a complete import.
"""

from __future__ import annotations

import importlib

_FAMILY_MODULES = [
    "catalog_fam_it",
    "catalog_fam_marketing",
    "catalog_fam_management",
    "catalog_fam_sales",
    "catalog_fam_logistics",
    "catalog_fam_finance_hr_admin",
    "catalog_fam_legal_security",
    "catalog_fam_healthcare",
    "catalog_fam_education",
    "catalog_fam_construction",
    "catalog_fam_industry",
    "catalog_fam_services",
    "catalog_fam_creative",
]

LOADED: list[str] = []
MISSING: list[str] = []
for _name in _FAMILY_MODULES:
    try:
        importlib.import_module(f"app.services.career_kb_mnp.{_name}")
        LOADED.append(_name)
    except ModuleNotFoundError as exc:  # pragma: no cover - dev-time incremental build
        if exc.name and exc.name.endswith(_name):
            MISSING.append(_name)
        else:
            raise
