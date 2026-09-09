# NAPRIAM / МОЖУ: Мій Напрям

## Структура та запуск

- `frontend/` — React + Vite + TypeScript; готова збірка в `frontend/dist/`.
- `backend/` — FastAPI, MongoDB runtime, моделі, тести та інструменти.
- `docs/` — документація, архітектура та архів вихідних вимог.

Для backend відкрийте **`backend/run.py` → Run Python File in Terminal**
або F5 → **ICAN: backend only**. Для frontend відкрийте термінал у
`frontend/` і виконайте **`npm run dev`**. Кожен процес зупиняється
через `Ctrl+C` у своєму терміналі. Старий `dev.py` залишено як необов’язковий
спільний запуск для сумісності.
Секрети тепер у `backend/.env`; робоча база — MongoDB `ican`.
SQLite-файл у `backend/data/dev/` збережений лише як джерело перенесених даних і rollback-копія. Наявне Python-середовище `.venv/`
залишається в корені; переносити його вручну не потрібно.

[Повна карта папок і правила запуску](docs/architecture/REPOSITORY_LAYOUT.md).

---

**NAPRIAM — кар’єрний навігатор для України.** Продукт допомагає людині зібрати реальний цифровий кар’єрний профіль, зрозуміти доступні професії та поетапно перейти до персональних сценаріїв розвитку.

Канонічний опис поточного стану: [`docs/product/CURRENT_SOURCE_OF_TRUTH.md`](docs/product/CURRENT_SOURCE_OF_TRUTH.md).

---

## Поточна продуктова модель

NAPRIAM будується навколо одного **Digital Career Profile**:

- **I CAN** — що людина реально вміє і має: досвід, освіта, навички, інструменти, мови, проєкти, сертифікати та evidence.
- **I AM** — що людині підходить: сильні сторони, інтереси, стиль роботи, цінності та мотивація. Методологія assessment ще не затверджена; зараз це visual/future layer.
- **I WANT** — чого людина хоче: формат роботи, географія, мобільність, цілі та майбутні кар’єрні пріоритети. Частина полів уже зберігається в Person KB.

Це **три проєкції однієї Person KB**, а не три окремі бази.

Майбутній Matching контракт:

`Capability Fit (I CAN) + Personal Fit (I AM) + Goal Fit (I WANT) + Transition Distance + Market Opportunity`

Matching methodology у поточному Product Shell не змінюється і новий Person → Matching адаптер ще не ввімкнений.

---

## Що вже працює

### Person KB

Канонічний Person root — `MnpPerson` (`mnp_persons`). В одну Person KB пишуть усі три робочі входи:

1. ручне створення профілю;
2. CV upload → extraction → review → confirm;
3. Admin CRUD.

Зберігаються контактні дані, досвід, освіта, credentials, активності/проєкти, навички та інструменти, мови, документи, мобільність і evidence state.

Person skills використовують спільний канонічний `mnp_skills` universe з Career KB.

### Career KB

Поточний канонічний стан:

- **150 професій**;
- **5 ACTIVE**;
- **145 DRAFT**.

Правила scope:

- **Public Career catalog:** тільки ACTIVE;
- **Admin Career KB:** усі 150;
- **internal Matching development/tests:** усі 150 можуть брати участь незалежно від publication status;
- DRAFT не публікується автоматично і не переводиться в ACTIVE без ручного review.

Career KB Editor + канонічна БД — operational source of truth. Excel — тільки review/export артефакт (`DB → Excel`).

### NAPRIAM Product Shell

Клієнтський SPA вже має єдину візуальну систему та повний product shell:

- Public Home;
- Як це працює;
- Про нас;
- Create Profile;
- CV flow;
- Manual Profile;
- My Profile;
- Digital Career Profile `I CAN / I AM / I WANT`;
- Public Career catalog + Career detail;
- Workspace shell;
- visual/future screens для Scenarios, What-if, Route, Action Plan, Progress, Insights, Premium, Coach, Consultation.

Функції, яких ще немає, не імітують backend: вони показані як `Незабаром`, future state або demo shell без fake live data.

---

## Що ще не реалізовано

Поки **не ввімкнені**:

- production email/password auth;
- Google / LinkedIn OAuth;
- LinkedIn import;
- Person → Matching adapter;
- Personal Fit / Goal Fit methodology;
- повноцінний Career Discovery assessment;
- Market KB (вакансії, зарплати, попит);
- Route Builder;
- Next Best Action engine;
- Action Plan / Progress logic;
- What-if simulator;
- Resources recommendation engine;
- Payments / checkout;
- Coach / consultation backend.

Принцип: **спочатку весь продукт спроєктований в одному UX, потім функціональність відкривається блок за блоком.**

---

## Admin

Admin залишається окремим внутрішнім інтерфейсом і не змішується з customer workspace.

Працюють:

- Person KB Admin;
- Career KB Admin / Editor;
- create / edit / archive;
- evidence/source inspection;
- Excel export workflows.

Future admin modules (Matching, Routes, Resources, Users, Consultations, Payments тощо) поки не реалізуються.

---

## Модель веток

| Ветка | Роль |
|---|---|
| `master` | стабільний legacy / release baseline |
| `product-system-v3.1` | **канонічна development/integration branch** |
| feature branches | короткоживучі; від `product-system-v3.1`, повертаються через PR |
| research / archive | `matching-v1-deterministic-core`, `data-foundation-v1`, `stage-3b-direction-intelligence-v1` |

`mnp-v1-implementation`, `career-kb-v1-final`, `mnp-career-kb-v1`, `mnp-data-explorer-v1` уже консолідовані в canonical history.

---

## Архітектурні правила

- Person KB: одна `MnpPerson`; не створювати паралельні Person databases.
- Career KB: 150 careers; publication status не дорівнює internal matching eligibility.
- Public не показує DRAFT careers.
- Matching не має вигадувати scores або career facts.
- Market data не вигадуються; поки немає Market KB — salary/demand/employer metrics не є live data.
- Research tooling не є production source of truth.
- Excel не редагує canonical KB; напрямок тільки `DB → Excel`.
- Схема БД змінюється тільки additive Alembic migrations.
- Secrets — тільки через `.env`; raw session token не зберігається.

---

## Швидкий старт

### 1. Необхідні програми

Перед першим запуском встановіть:

- Python 3.11 або 3.12;
- Node.js 20 або новіший;
- Git;
- доступ до MongoDB Atlas або іншого MongoDB-сервера.

### 2. Створення `backend/.env`

Файл `backend/.env.example` — це безпечний шаблон. Його не потрібно
видаляти або перейменовувати: створіть поруч копію з назвою `.env`.

PowerShell із кореня репозиторію:

```powershell
Copy-Item backend/.env.example backend/.env
```

Linux/macOS:

```bash
cp backend/.env.example backend/.env
```

Або через VS Code: скопіюйте `backend/.env.example`, вставте копію в папку
`backend/` і перейменуйте копію на `.env`.

Відкрийте `backend/.env` і заповніть щонайменше:

```env
MONGODB_URL=mongodb+srv://alioshkin75:RiseUp2002@riseup.erzxo.mongodb.net/
MONGODB_DATABASE=ican
JWT_SECRET=ICAN2026
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,https://ican-frontend-mu.vercel.app
```

Згенерувати `JWT_SECRET` можна командою:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Не публікуйте `backend/.env` і не надсилайте його в чат. Він уже внесений
до `.gitignore`. `backend/.env.example` зберігається в репозиторії без
справжніх паролів і ключів.

### 3. Запуск backend

Відкрийте перший термінал у корені репозиторію:

```powershell
cd backend
python run.py
```

`run.py` автоматично створить кореневе середовище `.venv`, встановить
відсутні залежності та запустить FastAPI на:

`http://127.0.0.1:8099`

Перевірка backend:

`http://127.0.0.1:8099/health`

Термінал із backend потрібно залишити відкритим. Для зупинки натисніть
`Ctrl+C` саме в цьому терміналі.

### 4. Запуск frontend

Не зупиняючи backend, відкрийте другий термінал у корені репозиторію:

```powershell
cd frontend
npm install
npm run dev
```

`npm install` обов'язково виконується після першого клонування або зміни
залежностей. Під час наступних запусків достатньо:

```powershell
cd frontend
npm run dev
```

Frontend відкриється на:

`http://127.0.0.1:5173/mnp/`

Vite локально проксіює API-запити на `http://127.0.0.1:8099`. Термінал із
frontend також залишайте відкритим; `Ctrl+C` зупиняє лише frontend.

### 5. Перший вхід

Відкрийте:

`http://127.0.0.1:5173/mnp/#/admin/login`

Якщо в MongoDB ще немає працівників, форма запропонує створити першого
користувача. Перший зареєстрований користувач автоматично стає
суперадміністратором. Наступні облікові записи створюються відповідно до
правил ролей у консолі.

### 6. Типові проблеми

- `MONGODB_URL is required` — не створено `backend/.env` або не заповнено URL;
- `JWT_SECRET is required` — у `backend/.env` немає `JWT_SECRET`;
- порт `8099` зайнятий — зупиніть старий backend через `Ctrl+C` або PM2;
- порт `5173` зайнятий — зупиніть попередній Vite-процес;
- `Failed to fetch` — переконайтеся, що backend працює і `/health` повертає
  `{"status":"ok"}`.

### 7. Production-збірка frontend

```powershell
cd frontend
npm run build
```

Готові файли з'являться у `frontend/dist/`.

Основні маршрути:

- Public: `http://127.0.0.1:8099/mnp/#/`
- Create Profile: `#/profile`
- Workspace: `#/app`
- Digital Career Profile: `#/app/profile`
- Public Careers: `#/catalog`
- Admin Login: `#/admin/login`
- Admin Person KB: `#/admin/persons`
- Admin Career KB: `#/admin/catalog`

Для входу використовуйте особистого суперадміна, створеного під час першого
запуску. Спільний демонстраційний вхід після цього не використовується.

### Ринок праці

Сторінка `#/market` використовує офіційний відкритий набір актуальних
вакансій Державної служби зайнятості з Data.gov.ua. Backend раз на добу
перевіряє CKAN metadata та завантажує великий XML лише тоді, коли з'явився
новий resource id. Імпорт потоковий; OpenAI/Anthropic не використовується.

Публічний зріз: `GET /v1/mnp/market/overview?region=Харківська область`.
Адміністратор також може запустити перевірку вручну:
`POST /v1/mnp/admin/market/refresh` з admin Bearer token.

Автооновлення налаштовується через `MARKET_DATA_AUTO_REFRESH` та
`MARKET_DATA_REFRESH_HOURS`. Показуються лише вакансії, які детерміновано
зіставлені з чинними назвами або aliases у Career KB; невідомі назви не
створюють нових професій автоматично.

---

## Excel

Career KB export (виконувати з `backend/`):

```bash
MNP_DATABASE_URL="sqlite+aiosqlite:///./data/dev/mnp_dev.sqlite" python -m data_explorer.cli export-careers-excel
```

Person KB має окремий Founder-readable export `MNP_PERSON_KB_V1.xlsx`.

Excel — review/export layer, не source of truth.

---

## Тести

```bash
pytest -q
```

SQLite regression працює локально. Повна migration chain на PostgreSQL перевіряється в CI (`postgres-migrations`).

---

## Research / tooling

`backend/data_explorer/` містить ESCO, O*NET, Work.ua inventory, crosswalk,
human lab та Excel tooling. Це переважно допоміжні інструменти;
CSV-довідник Work.ua також використовується наповненням Career KB.

Career Data Audit / ESCO-O*NET mapping залишається research-напрямом і не ускладнює поточний V1 runtime.

---

## Legacy / Foundation

Репозиторій виріс з ICAN 1.1 Screening MVP. Legacy Telegram screening, CRM, Identity/Consent та ранні Assessment/Evidence шари залишаються в кодовій базі як foundation/compatibility layer, але нова продуктова робота ведеться навколо NAPRIAM, Person KB та Career KB.

Для точного актуального статусу завжди використовувати [`docs/product/CURRENT_SOURCE_OF_TRUTH.md`](docs/product/CURRENT_SOURCE_OF_TRUTH.md).
