# Структура репозиторію ICAN

Це структурне впорядкування, а не зміна бази даних або продуктового scope.
Імена Python-модулів `app`, `scripts`, `data_explorer` та API-контракти збережені.

```text
ICAN/
├── frontend/
│   ├── src/                 React, сторінки, Redux, API-клієнт
│   ├── public/              статичні ресурси
│   ├── legacy/
│   │   ├── admin/           попередня адмінка /dashboard
│   │   └── mnp/             попередній сайт, fallback без React-збірки
│   ├── dist/                автоматична збірка, не в Git
│   └── package.json         залежності й команди frontend
├── backend/
│   ├── app/
│   │   ├── api/             FastAPI-маршрути та перевірка доступу
│   │   ├── bot/             Telegram-бот
│   │   ├── core/            конфігурація, безпека, стабільні шляхи
│   │   ├── db/              моделі та підключення до сховищ
│   │   ├── schemas/         контракти даних
│   │   └── services/        логіка профілів, професій, Matching, CRM
│   ├── scripts/             запуск, наповнення, налаштування власника
│   ├── run.py               окремий запуск backend кнопкою у VS Code
│   ├── migrations/          історія SQL-схеми
│   ├── tests/               автоматичні перевірки
│   ├── evals/               еталонні приклади
│   ├── data_explorer/       довідники, аналіз, Excel-інструменти
│   ├── data/                локальна база, резюме; не в Git
│   ├── artifacts/           діагностика та скриншоти; не в Git
│   ├── .env                 локальні секрети; не в Git
│   ├── .env.example         шаблон змінних
│   ├── requirements.txt     Python-залежності програми
│   ├── requirements-datalab.txt
│   ├── alembic.ini
│   └── docker-compose.yml   локальна PostgreSQL
├── docs/
│   ├── architecture/
│   ├── product/
│   └── archive/MNP_DEVELOPMENT_PACKAGE_V1/
├── .github/                 перевірки GitHub Actions
├── .vscode/                 запуск і налаштування редактора
├── .venv/                   наявне локальне Python-середовище, не в Git
├── dev.py                   єдина кнопка локального запуску
├── requirements.txt         лише посилання на backend/requirements.txt
├── pytest.ini               запуск усіх backend-тестів з кореня
├── Procfile                 команди web/worker для хостингу
├── .python-version          версія Python для середовища/хостингу
├── .gitignore
└── README.md
```

## Чому кілька службових файлів залишилися в корені

GitHub очікує `.github/workflows`, VS Code використовує `.vscode`.
Кореневі `requirements.txt` і `Procfile` зберігають стандартний вхід
для існуючого Python-хостингу. Список залежностей не дублюється:
кореневий файл лише включає файл бекенду.

`.venv` не переносили: у встановлених скриптах можуть бути абсолютні шляхи.
Кеші Python/pytest приховані у VS Code; це не вихідний код.

## Локальний запуск

Основний спосіб: `backend/run.py` → Run Python File in Terminal або
F5 → **ICAN: backend only**. Фронтенд: `npm run dev` з папки `frontend/`.
Кожен сервер працює й зупиняється через Ctrl+C у своєму терміналі.
Backend не запускає npm і не відкриває браузер. `dev.py` залишено як
необов’язковий спільний запуск для сумісності.
Backend запускається з робочою папкою `backend/`, frontend — з `frontend/`.
Вхід: `http://127.0.0.1:5173/mnp/#/admin/login`.
Наявна локальна база та ключ підписування перенесені разом у `backend/data/dev/`.
Не виконуйте `--reset` для звичайного запуску: він видаляє тестову базу.

Ручні Python-команди (`python -m scripts...`, `alembic`, `data_explorer`)
виконуються з `backend/` у віртуальному середовищі проєкту.
`Settings` читає саме `backend/.env` незалежно від робочої папки.

## Збірка та перевірки

З кореня, в активному Python-середовищі:

```bash
pip install -r requirements.txt
python -m pytest -q
npm --prefix frontend ci
npm --prefix frontend run build
```

React збирається в `frontend/dist/`; FastAPI віддає цю папку через `/mnp`.
GitHub CI перевіряє Python, SQL-міграції на тестовому PostgreSQL та React-збірку.

## Хостинг

Коренева папка розгортання — репозиторій, не лише `backend/`, якщо
FastAPI має віддавати також React і legacy-інтерфейси.
Build: Python-залежності плюс `npm --prefix frontend ci` і
`npm --prefix frontend run build`. `Procfile` переходить у `backend/`
перед запуском міграцій, API або бота. Налаштування хмарного середовища
не змінювалися автоматично, публікація не виконувалась.

Для локального PostgreSQL з кореня: `docker compose -f backend/docker-compose.yml up -d`.
Назву Compose-проєкту зафіксовано як `ican`, щоб перенесення файлу не
створювало інший стандартний volume. Якщо раніше використовували власний
параметр `-p`, продовжуйте використовувати саме його.
`dev.py` як і раніше використовує SQLite. MongoDB-підключення підготовлене,
але структурне перенесення не перемикає на нього зберігання CRM.

## Збережені старі матеріали

Старі frontend-версії не видалено: їхні маршрути залишені сумісними.
Після окремої перевірки функцій можна відмовитися від fallback і `/dashboard`.
Пакет із 44 вихідних документів повністю збережено в `docs/archive/`:
39 мали ідентичні копії у `docs/mnp_v1`, 5 там були відсутні.
Історичні документи можуть містити старі шляхи; актуальна карта — цей файл.
