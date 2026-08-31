# ICAN 1.1 — Screening MVP

Первый рабочий этап продукта ICAN: пользователь проходит первичный скрининг в
Telegram в формате естественного диалога, AI извлекает факты и превращает
разговор в структурированный профиль, пользователь подтверждает его, профиль и
история диалога сохраняются в PostgreSQL.

Архитектура: `Telegram → FastAPI → AI Screening (Claude) → PostgreSQL`.

## Структура проекта

```
app/
  bot/        # Telegram-бот (aiogram) — диалог, подтверждение/правки
  api/        # FastAPI — публичный API + Admin API (/admin/...) + раздача dashboard
  services/   # ScreeningAgent (вызов Claude) + CRUD профиля + admin_service
  db/         # SQLAlchemy модели и сессия
  schemas/    # Pydantic-схемы профиля + JSON-схема tool-use для Claude
  core/       # конфиг + auth (JWT, bcrypt)
admin_frontend/ # Admin Dashboard — SPA на чистом JS + Tailwind (без сборки)
migrations/   # Alembic
scripts/      # create_admin.py — завести логин админа/менеджера
tests/        # pytest (sqlite in-memory, без внешних сервисов)
```

## Быстрый старт

1. Установить зависимости:

   ```bash
   pip install -r requirements.txt
   ```

2. Скопировать `.env.example` в `.env` и заполнить:
   - `TELEGRAM_BOT_TOKEN` — токен от @BotFather
   - `ANTHROPIC_API_KEY` — ключ для AI Screening
   - `DATABASE_URL` — строка подключения к PostgreSQL

3. Поднять PostgreSQL локально (например, `docker compose up -d`, если Docker
   доступен, либо любой существующий инстанс — главное чтобы `DATABASE_URL`
   на него указывал).

4. Прогнать миграции:

   ```bash
   python -m alembic upgrade head
   ```

5. Запустить бота:

   ```bash
   python -m app.bot.main
   ```

6. Запустить API для просмотра профилей командой:

   ```bash
   uvicorn app.api.main:app --reload
   ```

   - `GET /users/{telegram_id}/profile` — структурированный профиль
   - `GET /users/{telegram_id}/messages` — исходный диалог скрининга

## CRM 1.0

Полноценная CRM для команды ICAN — единая карточка клиента, роли
ADMIN / MANAGER / CAREER_CONSULTANT, воронка NEW → SCREENING →
WAITING_CONSULTANT → CAREER_CONSULTATION → READY_FOR_MATCHING → IN_WORK /
PAUSED / CLOSED. Доступна на `/dashboard` того же FastAPI-сервиса (единый
деплой, без CORS).

1. Завести логины:

   ```bash
   python -m scripts.create_admin admin@example.com "a-strong-password" admin
   python -m scripts.create_admin manager@example.com "a-strong-password" manager
   python -m scripts.create_admin consultant@example.com "a-strong-password" career_consultant
   ```

2. Открыть `http://localhost:8000/dashboard/` и войти.

**Telegram-бот — один из каналов входа клієнта в CRM.** Когда пользователь
подтверждает профіль у боті, `app/services/crm/bridge.py` автоматично
створює/оновлює пов'язану картку `Client` і одразу переводить її на етап
`WAITING_CONSULTANT` — бот уже виконав «первинний скринінг», менеджеру не
треба робити це повторно. Дзвінки по телефону — інший канал: менеджер сам
створює клієнта і скринить його вручну.

**API** — під `/crm/*` (див. `app/api/crm.py`): клієнти зі списком/пошуком/
фільтрами/пагінацією, повторювані блоки (досвід/навички/мови), кар'єрна
консультація, дзвінки (поки що ручне логування — Phonet ще не підключено),
файли (CV/сертифікати — локальне сховище `app/services/crm/storage.py`,
легко замінити на S3/R2), задачі (Next Actions), timeline/аудит, керування
персоналом. RBAC перевіряється на бекенді: `CAREER_CONSULTANT` фізично не
може отримати чужого клієнта навіть напряму через API.

Старий простий `/admin/*` API (перегляд сирих даних бота) лишився робочим
і покритий тестами, але фронтенд тепер веде саме на CRM.

### Деплой на Railway

1. Запушить репозиторий на GitHub, создать проект на [railway.app](https://railway.app), подключить репозиторий.
2. Railway сам определит Python-проект по `requirements.txt` и запустит команду из `Procfile` (миграции + `uvicorn`).
3. В Variables прописать: `DATABASE_URL`, `JWT_SECRET` (и `ANTHROPIC_API_KEY`/`TELEGRAM_BOT_TOKEN`, если этот же сервис используется и для бота).
4. После первого деплоя выполнить `python -m scripts.create_admin ...` через Railway Shell (или локально, указав продовый `DATABASE_URL`), чтобы завести логин.
5. Dashboard будет доступен по `https://<project>.up.railway.app/dashboard/`.

## Локальный просмотр MNP (без Postgres)

Фронтенд «МОЖУ: Мій Напрям» (`mnp_frontend/`, роут `/mnp/`) можно поднять
на локальной SQLite-БД без Postgres/Docker. Схема строится из моделей
(как в тестах); прод-Postgres из `.env` при этом не трогается.

```bash
python -m scripts.dev_seed --serve
```

Один раз создаёт `data/dev/mnp_dev.sqlite`, наполняет Career KB (5 ACTIVE
профессий + импорт стартового каталога Work.ua = ~145 DRAFT), заводит
dev-админа и запускает API+фронтенд на `http://127.0.0.1:8099`.

- Публичный Career Explorer: `http://127.0.0.1:8099/mnp/#/catalog` (только ACTIVE)
- **Career KB Editor** (управление без кода): `http://127.0.0.1:8099/mnp/#/admin/login`,
  логин `admin@mnp.local` / `mnp-dev-admin`. После входа: `#/admin/catalog` —
  все профессии со статусами; «Редагувати» на карточке; «+ Створити професію».
- `--reset` — пересоздать dev-БД с нуля (после изменения схемы).
- `--serve --skip-seed` — только запустить сервер, БД не трогать.

**Career KB — источник истины.** База `mnp_*` + Career KB Editor —
единственный operational source of truth. `seed_alpha.py` и `seed_catalog.py`
— это только bootstrap: создают профессии, которых ещё нет, и **никогда** не
перезаписывают ручные правки админа. API, Matching, публичный сайт и
Excel-экспорт читают ту же БД.

**Work.ua Career Guide = discovery source only** (не источник контента).
Инвентарь профессий: `data_explorer/workua/inventory/` (снапшот 2026-08-31,
149 профессий). Пере-краул и diff (БД не трогает):
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

Тесты не требуют Postgres/Telegram/Anthropic — используют in-memory SQLite и
замоканный Claude-клиент.

## Ключевые правила (из ТЗ)

- AI никогда не выдумывает факты — если данные не названы пользователем,
  поле остаётся пустым (`app/services/screening.py`, системный промпт).
- Уже известные факты не переспрашиваются повторно.
- Профиль подтверждается пользователем перед сохранением как финальный
  (`confirmed=True`); до этого это черновик.
- Секреты не коммитятся — только через `.env` (см. `.gitignore`).
- Схема БД меняется только через Alembic-миграции.

## Что не входит в 1.1

Поиск вакансий, matching, база работодателей, отправка/генерация CV,
подготовка к собеседованию, автоконтакт с работодателем, сложная админка,
мобильное приложение — переносится на следующие версии (ICAN 1.2+).
