# ICAN backend

FastAPI, Telegram-бот, моделі, сервіси, тести та інструменти проєкту.

Для звичайної роботи відкрийте `run.py` у VS Code і натисніть
**Run Python File in Terminal**, або виберіть F5 → **ICAN: backend only**.
Запускається лише бекенд на `http://127.0.0.1:8099`, без npm і браузера.
`Ctrl+C` зупиняє його в цьому ж терміналі.
Backend підключається лише до MongoDB з `MONGODB_URL`. Якщо у базі ще немає
суперадміністратора, форма першого запуску з'явиться на сторінці входу.
Фронтенд запускайте незалежно: `npm run dev` з папки `frontend/`.
Секрети: `.env` у цій папці. Залежності: `requirements.txt`.
Для хостингу обов'язково задайте `MONGODB_URL`, `MONGODB_DATABASE=ican`
та довгий стабільний `JWT_SECRET`.

Команди `python -m scripts.check_mongodb`,
`python -m scripts.migrate_sqlite_to_mongodb` та `python -m data_explorer.cli ...` виконуються з цієї папки
в активованому середовищі `../.venv`.

Усі тести: `python -m pytest -q` з кореня репозиторію.
[Карта структури та розгортання](../docs/architecture/REPOSITORY_LAYOUT.md).
