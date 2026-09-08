# MongoDB: connection prepared, application migration not enabled

Target database name: `ican`. Credentials belong only in the ignored `backend/.env`
or hosting environment variables. Do not copy Telegram/OpenAI/webhook settings
from a different application just to enable database connectivity.

## Implemented

- `MONGODB_URL` is a masked `SecretStr`; `MONGODB_DATABASE` defaults to `ican`.
- `backend/app/db/mongo.py` provides a bounded async PyMongo connection with cleanup.
- From `backend/`, `python -m scripts.check_mongodb` runs ping and lists collection names in the
  selected database, but only reports the number of collections. No writes,
  document reads, automatic migration, database creation or deletion.
- Unit tests use fake clients and never connect to the cloud.

Driver reference: [PyMongo connection documentation](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/connect/).

## Not switched yet

`dev.py` still runs the existing SQLite development environment. Other backend
launches still use SQLAlchemy and `DATABASE_URL`. Merely configuring MongoDB
does not migrate accounts or profiles. MongoDB has no second person model and
there is no dual-write implementation.

Before cutover, explicitly decide whether existing local/test records should
be transferred or whether the cloud workspace starts empty. Never overwrite
existing cloud collections or migrate unrelated databases implicitly.

## Migration order and acceptance checks

1. Keep the canonical MnpPerson fields, UUIDs, facts and evidence/provenance;
   introduce repository boundaries for existing services instead of creating
   a second Client/Person model.
2. Adapt staff storage and owner bootstrap, preserving password hashes, role
   hierarchy, immediate deactivation and explicit person access grants.
3. Verify login → list → create → edit → save → reopen against real MongoDB,
   with isolation tests for managers and concurrent access changes.
4. Adapt shared identity/session storage, Career KB, skill taxonomy, Matching,
   market statistics/export, audit and other SQL-backed services. Do not
   present an isolated Mongo console as a completed whole-system migration.
5. Transfer approved data with a repeatable, non-destructive import; preserve
   IDs and references and validate counts/integrity before changing launchers.
6. Switch `dev.py` and hosting only when the affected scenarios and tests pass.
   Retain the old database for rollback; no automatic deletion.
