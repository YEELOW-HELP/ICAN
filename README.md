# МОЖУ / MNP

**Статус:** активная разработка продукта **«МОЖУ: Мій Напрям»** (career navigation для украинского рынка — детерминированный, объяснимый, без выдуманных цифр).

Единый источник того, что канонично **сегодня**: [`docs/product/CURRENT_SOURCE_OF_TRUTH.md`](docs/product/CURRENT_SOURCE_OF_TRUTH.md).

Репозиторий вырос из **ICAN 1.1 — Screening MVP** (Telegram-скрининг). Тот слой остаётся рабочим фундаментом — см. раздел [Legacy / Foundation](#legacy--foundation).

---

## Модель веток

| ветка | роль |
|---|---|
| `master` | стабильный legacy / release baseline (ICAN era) |
| `product-system-v3.1` | **единственная** каноническая ветка разработки/интеграции текущего продукта МОЖУ / MNP |
| feature-ветки | короткоживущие, от `product-system-v3.1`, вливаются обратно через PR |
| research / archive | `matching-v1-deterministic-core`, `data-foundation-v1`, `stage-3b-direction-intelligence-v1` — история и исследования, **не** вливаются в прод |
| temporary / superseded | `stage-1-hotfix-anthropic-key-validation` — старый хотфикс; его полезное поведение уже перенесено в `repo-cleanup-v1`. Удаляется после merge PR #24; **не** постоянная research/archive-ветка |

`mnp-v1-implementation`, `career-kb-v1-final`, `mnp-career-kb-v1`, `mnp-data-explorer-v1` — уже консолидированы в `product-system-v3.1` и удалены.

---

## Слои продукта

### FOUNDATION (переиспользуется)

- **Identity / Consent** — пользователь, согласие, идентификация
- **Assessment** — гибридный ассессмент (Stage 1)
- **Evidence / Profile** — доказательный профиль потенциала (Stage 2)
- **Knowledge** — Stage 3A Career Knowledge Base (legacy-таксономия)
- **CRM** — единая карточка клиента, роли, воронка (`/dashboard`)

### MNP V1 — ТЕКУЩЕЕ

- **Career Card** — публичная карточка профессии
- **Career KB** — каноническая база профессий (`mnp_*` таблицы)
- **Career KB Admin / Editor** — управление базой без кода (`/v1/mnp/admin/*`, `#/admin/*`)
- **Career Explorer** — публичный каталог + карточка (`/mnp/#/catalog`)
- **Questionnaire** — минимальный опросник
- **Resume parser** — резюме → CareerCard
- **Matching / Transition** — детерминированный движок (`app/services/matching/`), без AI
- **MNP frontend** — `mnp_frontend/`, чистый JS, без сборки

### RESEARCH / TOOLING (не рантайм)

- `data_explorer/` — исследовательский data-lab: ESCO, O*NET, Work.ua inventory, crosswalk, human lab, Excel-экспорт
- `evals/` — golden-датасеты и инструменты

> **Research tooling — это НЕ канонический рантайм Career KB.**
> `data_explorer/` может **читать** каноническую БД; продакшн-рантайм от `data_explorer/` **не зависит**.
> Career Data Audit / ESCO-O*NET mapping — исследование, отложено, **не** входит в текущий V1-рантайм.

---

## Career KB — каноническое состояние

- **150 профессий · 5 ACTIVE · 145 DRAFT**
- DRAFT не показываются на публичном сайте и не участвуют в matching.
- Каноническая БД `mnp_*` + Career KB Editor — **единственный** operational source of truth.
- Excel `MNP_CAREER_KB_V1.xlsx` — **артефакт review/экспорта, НЕ источник истины**. Путь только DB → Excel.
- Никаких выдуманных рыночных данных: каждая профессия `MARKET_DATA_LIMITED`, метрики пустые.

**Market KB** (вакансии, зарплаты, спрос) — **отложен**, ещё не канонический.

**Person KB** — следующий архитектурный workstream: перед реализацией нужно согласовать переиспользование существующих Identity / Assessment / Evidence / Profile / Knowledge. **Этой задачей не реализуется.**

---

## Быстрый старт (MNP, без Postgres)

Фронтенд «МОЖУ: Мій Напрям» (`mnp_frontend/`, роут `/mnp/`) поднимается на локальной SQLite — схема строится из моделей (как в тестах), прод-Postgres из `.env` не трогается.

```bash
pip install -r requirements.txt
python -m scripts.dev_seed --serve
```

Один раз создаёт `data/dev/mnp_dev.sqlite`, наполняет Career KB (5 ACTIVE + импорт стартового каталога Work.ua ≈ 145 DRAFT), заводит dev-админа, поднимает API + фронтенд на `http://127.0.0.1:8099`.

- Публичный Career Explorer: `http://127.0.0.1:8099/mnp/#/catalog` (только ACTIVE)
- **Career KB Editor:** `http://127.0.0.1:8099/mnp/#/admin/login` — `admin@mnp.local` / `mnp-dev-admin` → `#/admin/catalog`
- `--reset` — пересоздать dev-БД (после изменения схемы); `--serve --skip-seed` — только сервер

**seed — только bootstrap.** `seed_alpha.py` / `seed_catalog.py` создают недостающие профессии и **никогда** не перезаписывают ручные правки админа.

**Work.ua Career Guide = discovery source only** (не источник контента). Инвентарь: `data_explorer/workua/inventory/`. Пере-краул + diff (БД не трогает):

```bash
python -m data_explorer.cli refresh-workua-career-inventory
```

**Excel со всем KB** (150 профессий) — против dev-БД:

```bash
MNP_DATABASE_URL="sqlite+aiosqlite:///./data/dev/mnp_dev.sqlite" python -m data_explorer.cli export-careers-excel
```

## Тесты

```bash
pytest -q
```

In-memory SQLite, замоканный Claude-клиент. Postgres / Telegram / Anthropic не нужны. Полная миграционная цепочка на реальном Postgres проверяется в CI (`postgres-migrations`).

## Ключевые правила

- AI никогда не выдумывает факты — не названо пользователем, поле пустое.
- Никаких выдуманных рыночных цифр (`MARKET_DATA_LIMITED`).
- Схема БД меняется только через Alembic; миграции при обычной feature-разработке не сквошатся.
- Секреты — только через `.env` (см. `.gitignore`). `ANTHROPIC_API_KEY` валидируется рано (ASCII, без пробелов; секрет не попадает в текст ошибки).
- Career KB: правки только через Editor / БД; Excel регенерируется по запросу.

---

## Legacy / Foundation

### ICAN 1.1 — Screening MVP

Первый рабочий этап: пользователь проходит первичный скрининг в Telegram в формате естественного диалога, AI извлекает факты и превращает разговор в структурированный профиль, пользователь подтверждает его, профиль и история сохраняются в PostgreSQL.

Архитектура: `Telegram → FastAPI → AI Screening (Claude) → PostgreSQL`.

```
app/
  bot/        # Telegram-бот (aiogram)
  api/        # FastAPI — публичный API + Admin + CRM + раздача SPA
  services/   # ScreeningAgent + CRUD профиля + CRM + MNP
  db/         # SQLAlchemy модели и сессия
  schemas/    # Pydantic-схемы + JSON-схема tool-use
  core/       # конфиг + auth (JWT, bcrypt)
admin_frontend/ # Admin Dashboard (чистый JS + Tailwind)
mnp_frontend/   # МОЖУ / MNP SPA
migrations/     # Alembic
data_explorer/  # research / tooling
tests/          # pytest
```

Запуск legacy-бота и API:

```bash
cp .env.example .env    # TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, DATABASE_URL
python -m alembic upgrade head
python -m app.bot.main
uvicorn app.api.main:app --reload
```

### CRM 1.0

Полноценная CRM для команды — единая карточка клиента, роли ADMIN / MANAGER / CAREER_CONSULTANT, воронка NEW → SCREENING → WAITING_CONSULTANT → CAREER_CONSULTATION → READY_FOR_MATCHING → IN_WORK / PAUSED / CLOSED. На `/dashboard` того же FastAPI-сервиса (единый деплой, без CORS). API — под `/crm/*` (`app/api/crm.py`), RBAC на бэкенде. Логины: `python -m scripts.create_admin <email> <password> <role>`.

Telegram-бот — один из каналов входа: при подтверждении профиля `app/services/crm/bridge.py` создаёт/обновляет карточку `Client` и переводит на `WAITING_CONSULTANT`.

### Деплой на Railway

Railway определяет Python-проект по `requirements.txt`, запускает `Procfile` (миграции + `uvicorn`). В Variables: `DATABASE_URL`, `JWT_SECRET`, при необходимости `ANTHROPIC_API_KEY` / `TELEGRAM_BOT_TOKEN`. Dashboard: `https://<project>.up.railway.app/dashboard/`.
