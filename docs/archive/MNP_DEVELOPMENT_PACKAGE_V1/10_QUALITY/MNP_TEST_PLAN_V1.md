# MNP TEST PLAN V1

Unit:
parsers, normalization, scoring, feasibility, transition, gaps.

Integration:
CV→CareerCard; KB→engine; market snapshots; versioning; admin publish.

E2E:
with CV, without CV, reset/new run, edit Career Card/recalculate, limited market data, blocked career.

Security:
upload validation, authz, admin permissions, deletion, rate limits.

Data:
referential integrity, duplicate aliases, missing sources, stale snapshots, archived careers.

Regression:
Golden Dataset on every matching-engine/KB release.
