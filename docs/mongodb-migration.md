# MongoDB runtime і перенесення даних

Target database name: `ican`. Credentials belong only in the ignored `backend/.env`
or hosting environment variables. Do not copy Telegram/OpenAI/webhook settings
from a different application just to enable database connectivity.

## Implemented

- `MONGODB_URL` is a masked `SecretStr`; `MONGODB_DATABASE` defaults to `ican`.
- `backend/app/db/mongo.py` provides a bounded async PyMongo connection with cleanup.
- `app.mongo_runtime.main` — production web runtime без SQLAlchemy/asyncpg.
- Авторизація, ролі, клієнти, доступ менеджерів, Person KB, Career KB,
  ринкова статистика й Excel export читають та пишуть MongoDB.
- `python -m scripts.migrate_sqlite_to_mongodb` переносить усі таблиці,
  зберігаючи IDs і зовнішні посилання. Без `--replace` заповнені колекції
  пропускаються; джерельний SQLite ніколи не видаляється.

Driver reference: [PyMongo connection documentation](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/connect/).

## Cutover

`backend/run.py` і `Procfile` запускають Mongo-only runtime. PostgreSQL service
видалений з Docker Compose. Старі SQL модулі та міграції лишаються тільки як
тимчасова rollback-історія і не імпортуються production web процесом.

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
