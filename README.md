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
  api/        # FastAPI — просмотр профиля и истории команды
  services/   # ScreeningAgent (вызов Claude) + CRUD профиля
  db/         # SQLAlchemy модели и сессия
  schemas/    # Pydantic-схемы профиля + JSON-схема tool-use для Claude
  core/       # конфиг (переменные окружения)
migrations/   # Alembic
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
