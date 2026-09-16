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
Для прикріплення CV працівниками заповніть у цьому `.env` `DROPBOX_ROOT`,
`DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET` і `DROPBOX_REFRESH_TOKEN` (також на
сервері). Dropbox app має мати права `files.content.write` та
`files.content.read`; файли зберігаються приватно, без shared links.
Для кнопки «Проаналізувати» окремо потрібен `OPENAI_API_KEY` на
бекенді та `CV_ANALYSIS_ENABLED=true`. У картці клієнта кнопка
«Проаналізувати» дає вибір між прикріпленим CV і заповненою анкетою.
Аналіз CV працює з PDF із текстовим шаром і DOCX; старий DOC можна
зберегти, але перед аналізом його слід конвертувати. AI-пропозиції
кешуються за вибраним джерелом. Лише навички, назва яких точно збігається
з чинним записом `mnp_skills` і для яких у джерелі знайдено текстове
підтвердження, додаються в `mnp_person_skills_v1` як `system_detected`
(непідтверджені теги). Ручні навички не перезаписуються, повторний аналіз
не створює дублікати. Інші AI-пропозиції не записуються в профіль.
Для хостингу обов'язково задайте `MONGODB_URL`, `MONGODB_DATABASE=ican`
та довгий стабільний `JWT_SECRET`. У `CORS_ORIGINS` вкажіть точну адресу
фронтенду без кінцевого `/`, наприклад `https://ican-frontend-mnu.vercel.app`.

Команди `python -m scripts.check_mongodb`,
`python -m scripts.migrate_sqlite_to_mongodb` та `python -m data_explorer.cli ...` виконуються з цієї папки
в активованому середовищі `../.venv`.

Усі тести: `python -m pytest -q` з кореня репозиторію.
[Карта структури та розгортання](../docs/architecture/REPOSITORY_LAYOUT.md).
