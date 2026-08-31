# Career KB V1 — Founder Acceptance

Модуль **«Професії»** першого продукту MNP. Простий, керований, якісний
довідник професій, достатній для V1.

Base commit: `c0a14ba` · Branch: `career-kb-v1-final` · Acceptance status:
**AWAITING FOUNDER SIGN-OFF**

---

## 1. Purpose

V1 відповідає користувачу на одне питання:

> «Що це за професія і що потрібно, щоб у ній працювати?»

Career KB дає структуровану цифрову картку професії. Для Matching
потрібен структурований canonical Career KB — але **не** потрібен
складний runtime-двигун зовнішніх доказів.

## 2. Source of Truth

**Canonical Career KB (`mnp_*` таблиці) = єдине джерело істини.**

| шар | роль | runtime-залежність Career KB |
|---|---|---|
| Career KB (`mnp_careers` + діти) | сама база | — |
| Career KB Editor (`/v1/mnp/admin/*`) | керування без коду | — |
| ESCO / O*NET / WEF / Work.ua (`data_explorer/`) | research / reference | **НЕМАЄ** |
| Excel `MNP_CAREER_KB_V1.xlsx` | читабельний експорт | **НЕМАЄ** (DB → Excel, не навпаки) |

Правило залежності:

```
Data Explorer / Research   ──може читати──▶   Career KB
Career KB (production)      ──НЕ залежить──▶   Data Explorer / ESCO / O*NET
```

Career Data Audit (складний зовнішній evidence-двигун) **НЕ входить у
V1** — див. §13.

## 3. Career Card Schema

`mnp_careers` + діти. Внутрішня схема — English-first; людський контент —
**Ukrainian-first**.

| блок | таблиця | V1 |
|---|---|---|
| Identification | `mnp_careers` (`code`, `canonical_name_uk/en`, `career_family_id`, `status`, `career_profile_version`) + `mnp_career_aliases` | ✅ |
| Description | `description_short_uk`, `description_long_uk` | ✅ |
| Responsibilities | `mnp_career_tasks` (`title_uk`, `importance`, `sort_order`) | ✅ |
| Skills / Tools | `mnp_career_skill_requirements` → `mnp_skills` (canonical taxonomy) — `importance`, `required_level`, `requirement_type` | ✅ |
| Knowledge | `mnp_career_knowledge_requirements` → `mnp_knowledge` | ✅ (розріджено — §12, Known Limitations) |
| Entry requirements | `mnp_career_requirements` (`category` education/experience/credential/language/legal/other, `hardness` soft/hard) | ✅ (усі SOFT у V1) |
| Entry without experience | `mnp_careers.entry_without_experience` (yes / limited / no / unknown) + `difficulty_level` + `typical_entry_route_uk` | ✅ |
| Career path / transitions | `mnp_career_path_steps` (впорядкований типовий шлях) + `mnp_career_relations` (близькі професії / переходи) | ✅ (простий, без доказового графа) |
| Pros / Cons | `mnp_career_pros_cons` (редакційний шар) | ✅ |
| Sources / editorial note | `source` / `source_version` / `confidence` на кожному рядку + `mnp_external_mappings` | ✅ (провенанс на рядку, не окрема таблиця) |

**Skill taxonomy** — `mnp_skills` є спільною canonical-таксономією. Career
Skills і майбутні Person Skills вказуватимуть на ті самі canonical-терміни
(`PersonSkill → canonical term ← CareerSkill`). Новий Skill-universe не
створюється.

## 4. DRAFT / ACTIVE lifecycle

`CareerLifecycleStatus`: `DRAFT → VALIDATED → ACTIVE → REVIEW_DUE →
ARCHIVED`.

| стан | публічний сайт | production matching |
|---|---|---|
| DRAFT | ❌ приховано | ❌ виключено |
| ACTIVE | ✅ | ✅ |
| ARCHIVED | ❌ | ❌ |

* Публічний `GET /v1/mnp/careers` та `GET /v1/mnp/careers/{id}` віддають
  **лише ACTIVE**.
* Поточний стан: **5 ACTIVE · 145 DRAFT**. 145 DRAFT **не** публікуються
  автоматично — кожну публікує людина.

## 5. Admin workflow

Career KB Editor — `#/admin/login` → `#/admin/catalog`.

Адміністратор може:

1. відкрити список усіх 150 професій, фільтрувати за статусом / пошуком;
2. відкрити будь-яку професію → 10 вкладок (Основне, Обов'язки, Навички,
   Знання, Вимоги, Кар'єрний шлях, Переваги та недоліки, Пов'язані
   професії, Зовнішні відповідники, Джерела / Історія);
3. редагувати будь-яке поле; додати / видалити / переупорядкувати рядки;
4. зберегти → `career_profile_version` +1, один рядок в `audit_logs`
   (хто / коли / старе → нове);
5. «+ Створити професію» → порожня картка → зберегти як **DRAFT**;
6. «Опублікувати» (DRAFT → ACTIVE) — з перевіркою мінімальної повноти
   (назва, код, короткий + повний опис, ≥1 обов'язок, ≥1 навичка);
7. «Архівувати» / «Повернути з архіву».

**`career_code` незмінний після створення** — Editor не дає його
редагувати.

**Seed — bootstrap-only.** `seed_alpha` створює лише відсутні alpha-кар'єри;
`seed_catalog` пропускає будь-яку професію, чий `code` вже існує. Повторний
`python -m scripts.dev_seed` **не відкочує** жодну ручну зміну.

## 6. Excel workflow

```
python -m data_explorer.cli export-careers-excel          # alpha (5) з in-memory seed
MNP_DATABASE_URL=sqlite+aiosqlite:///./data/dev/mnp_dev.sqlite \
    python -m data_explorer.cli export-careers-excel      # повний dev KB (150)
```

→ `data/data_explorer/exports/MNP_CAREER_KB_V1.xlsx` (gitignored,
регенерований на вимогу).

**Excel = readable/exported view, НЕ паралельна master-БД. Немає шляху
Excel → DB.** Зміни робляться через Career Admin / DB.

Листи: `00_README, 10_CAREERS, 20_SKILLS, 25_KNOWLEDGE, 30_REQUIREMENTS,
40_RESPONSIBILITIES, 50_CAREER_PATHS, 60_PROS_CONS, 70_MARKET_DATA,
80_ALIASES, 85_EXTERNAL_REFS, 90_PROVENANCE`. Усі листи Ukrainian-first
(українські колонки — перші). `UNKNOWN ≠ 0`. Жодних вигаданих ринкових
цифр.

## 7. Ukrainian-first rule

* Internal: `code`, enum-значення, `name_en` — англійська.
* Human-readable: описи, обов'язки, навички (`canonical_name_uk`), вимоги,
  переваги/недоліки, кроки шляху — **українська**.
* Виняток — сталі власні назви інструментів/технологій: `Excel`, `SQL`,
  `Git`, `HTML`, `Adobe …`, `Data Scientist` — не перекладаються.

QA-результат (150 професій): 0 описів без кирилиці · 1 назва професії без
кирилиці (`Data Scientist`, легітимно) · 10/426 навичок без кирилиці (усі
— назви інструментів). **PASS.**

## 8. Required fields (для публікації DRAFT → ACTIVE)

`name_uk` · `career_code` · `description_short_uk` · `description_long_uk`
· ≥1 responsibility · ≥1 skill.

## 9. Optional fields

`name_en` · knowledge · requirements понад мову · pros/cons · career path
· relations · aliases понад авто-створений ринковий заголовок · external
mappings.

## 10. Founder manual review checklist (процедура V1)

Для кожної DRAFT-професії перед публікацією людина перевіряє:

- [ ] Назва — коректна українська ринкова назва
- [ ] Опис — зрозумілий, професійний, що це і чим займається людина
- [ ] Обов'язки — реально належать цій професії
- [ ] Навички / інструменти — достатні, без дублів, canonical-таксономія
- [ ] Знання — потрібні (лише якщо предметний блок є умовою входу)
- [ ] Вимоги до входу — реалістичні; HARD лише з авторитетним джерелом
- [ ] Можливість старту без досвіду — логічна
- [ ] Кар'єрний розвиток / переходи — логічні
- [ ] Джерела / редакторська перевірка — зафіксовано
- [ ] Дані виглядають коректно для українського користувача

Після перевірки людина натискає **«ОПУБЛІКУВАТИ»**. Окремий workflow-двигун
для чекліста не будується — це задокументована процедура V1.

## 11. 5 reference careers — QA

| професія (`code`) | опис | обов'язки | навички | знання | вимоги | шлях | мова | DB=API=Admin=Public=Excel |
|---|---|---|---|---|---|---|---|---|
| Бухгалтер (`accountant`) — ACTIVE | ✅ | 8 | 10 (2 must_have, tools: Excel / 1С:Бухгалтерія) | 3 (податкове зак-во, П(С)БО, труд. зак-во) | 4 SOFT (освіта / досвід / CAP-CIPA перевага / мова) | 5 кроків | ✅ | consistent |
| Менеджер з продажу (`sales_manager`) — ACTIVE | ✅ | 8 | 14 (B2B, воронка, переговори, CRM) | 0 | 3 SOFT | 5 | ✅ | consistent |
| Розробник ПЗ (`software_developer`) — ACTIVE | ✅ | 8 | 13 (Python, backend, SQL, Git, REST API) | 1 | 3 SOFT (портфоліо / освіта перевага / англ. читання) | 5 | ✅ | consistent |
| Координатор логістики (`logistics_coordinator`) — ACTIVE | ✅ | 8 | 12 (планування, WMS, Incoterms-суміжне) | 1 (Incoterms) | 3 SOFT | 5 | ✅ | consistent |
| Спеціаліст з обслуговування клієнтів (`customer_service_representative`) — ACTIVE | ✅ | 7 | 11 (обслуговування, активне слухання, конфлікти, емпатія) | 1 | 3 SOFT | 5 | ✅ | consistent |

**Знайдені зауваження** (не блокують acceptance):

1. `sales_manager` має 0 записів knowledge. Прийнятно у V1 (продажі —
   переважно навички), але методолог може додати «Основи договірного
   права» / «Продуктова експертиза».
2. Knowledge загалом розріджено — 5/150 професій. Це **навмисно** (§7.5
   брифу: «не заповнювати штучно заради completeness»), корінь описано в
   §12.
3. Усі вимоги — SOFT. Правильно для цих 5 (жодна не ліцензована). Для
   регульованих професій каталогу HARD-вимога потребує авторитетного
   UA-джерела — не додається editorial-інференсом.
4. `entry_without_experience`: accountant=limited, sales=yes, dev=limited,
   logistics=limited, CS=yes — логічно.

## 12. Known limitations

1. **Knowledge розріджено (5/150).** Корінь: `catalog_data.py` не має поля
   `knowledge`, `seed_catalog.py` не створює knowledge-зв'язків. Схема
   (`mnp_career_knowledge_requirements`) є і працює — 5 alpha-професій її
   використовують. Для 145 DRAFT знання додаються вручну через Editor там,
   де вони справді визначальні.
2. **Skill taxonomy — 426 canonical-навичок, є дублі/варіанти** (напр.
   переклади, `alias`-як-canonical). Не блокує V1; прибирати вручну через
   Editor у міру ревью професій.
3. **Ринкові дані відсутні** — кожна професія `MARKET_DATA_LIMITED`,
   `70_MARKET_DATA` порожній. Це навмисно (§8) — Market KB Ukraine —
   окремий наступний блок.
4. **`mnp_external_mappings` майже порожня** (2 рядки). ESCO/O*NET
   відповідники — не runtime-залежність V1; заповнюються research-шаром
   пізніше.
5. **145 DRAFT-професій — editorial-контент, не пройдений ручним ревью
   Founder/методолога.** Кожна лишається DRAFT до §10-чекліста.

## 13. What is deliberately postponed

- Advanced ESCO / O*NET mapping (mapping relation model, evidence usage)
- Automated Career Data Audit (складний зовнішній evidence-двигун,
  5000+ findings, P0/P1/P2, mapping review workflow) — реалізація існує
  лише в несмерженій експериментальній гілці `career-kb-data-audit-v1`,
  **у V1 не входить**
- Market KB Ukraine (вакансії, зарплати, попит, тренди)
- Live vacancy parsing / Work.ua live market data
- Advanced route validation (доказовий transition-граф)
- Person KB Base V1 (наступний блок; спільна skill-таксономія вже готова
  до нього)

## 14. Acceptance status

**AWAITING FOUNDER SIGN-OFF.**

Founder має відкрити:

1. публічний сайт (`#/catalog`, картку «Бухгалтер»);
2. Career Admin (`#/admin/catalog`, редагування «Бухгалтер», створення
   тестової DRAFT-професії);
3. 5 reference-професій;
4. `MNP_CAREER_KB_DATA_AUDIT_V1.xlsx` → `MNP_CAREER_KB_V1.xlsx`.

і зафіксувати: **CAREER KB V1 — FOUNDER ACCEPTED.**
