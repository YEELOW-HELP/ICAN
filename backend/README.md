# ICAN backend

FastAPI, Telegram-бот, моделі, сервіси, тести та інструменти проєкту.

Для звичайної роботи відкрийте `run.py` у VS Code і натисніть
**Run Python File in Terminal**, або виберіть F5 → **ICAN: backend only**.
Запускається лише бекенд на `http://127.0.0.1:8099`, без npm і браузера.
`Ctrl+C` зупиняє його в цьому ж терміналі.
Перший запуск за потреби налаштовує локальну базу й особистого суперадміна.
Фронтенд запускайте незалежно: `npm run dev` з папки `frontend/`.
Якщо потрібно створити superadmin, виконайте окремо:
`python -m scripts.console_setup --ensure`.
Для запуску backend із цим setup можна використати `python run.py --setup-admin`.
Секрети: `.env` у цій папці. Залежності: `requirements.txt`.
Не переносіть і не перезаписуйте наявну базу вручну.

Команди `python -m scripts.console_setup`, `python -m scripts.check_mongodb`,
`python -m data_explorer.cli ...` та `alembic ...` виконуються з цієї папки
в активованому середовищі `../.venv`.

Усі тести: `python -m pytest -q` з кореня репозиторію.
[Карта структури та розгортання](../docs/architecture/REPOSITORY_LAYOUT.md).
