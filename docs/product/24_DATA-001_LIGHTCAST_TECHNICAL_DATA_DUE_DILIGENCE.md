# DATA-001 — Lightcast Technical / Data Due Diligence

> **Тип документа:** техническая + продуктовая + коммерческая due diligence одного внешнего data-вендора.
> **Решение, которое документ должен закрыть:** BUILD vs BUY vs PARTNER для компонентов Career Intelligence Engine продукта «МОЖУ: Мій Напрям».
> **Дата исследования:** 29 августа 2026.
> **Автор роли:** Senior Product Architect + Labour Market Data Scientist + API/Data Due Diligence Analyst.
> **Статус:** DRAFT v0.1 — требует созвона с Lightcast для снятия блока `MUST ASK LIGHTCAST`.
> **Связанные документы:** [22_COMPETITIVE_ANALYSIS_AND_GOLDEN_TEST_TZ.md](22_COMPETITIVE_ANALYSIS_AND_GOLDEN_TEST_TZ.md), [20_MATCHING_V1_FOUNDER_DEFINITION.md](20_MATCHING_V1_FOUNDER_DEFINITION.md), [14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md](14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md).

---

## Условные обозначения достоверности

| Маркер | Значение |
|---|---|
| `CONFIRMED` | Подтверждено официальной документацией Lightcast / legal-документом / проверяемым внешним источником. Ссылка приведена. |
| `INFERENCE` | Наш вывод из совокупности фактов. Логичен, но прямого подтверждения нет. |
| `UNKNOWN` | Публичной информации недостаточно. Не гадаем. |
| `MUST ASK LIGHTCAST` | Критично для решения. Обязательно подтвердить напрямую на созвоне. |

**Главное методологическое правило этого документа:** глобальное присутствие Lightcast (165+ стран) ≠ доступность конкретных данных по Украине. Каждый датасет проверяется по Украине отдельно.

**Второе правило (жёсткий критерий Founder):** вывод «Lightcast подходит» имеет право на существование только если сквозная цепочка из §20 (CV украинца → нормализация → skills → текущая профессия → 5 переходов → skill gaps → украинский спрос → зарплата → реальные вакансии) реально собирается на 70–80%. Иначе документ обязан показать, какой слой мы строим сами.

**Дисклеймер об идентичности вендора:** речь идёт о **Lightcast** — рынок труда, `lightcast.io` (бывш. Emsi Burning Glass). НЕ путать с `lightcast.com` (обработка платежей) и `lightcast.bio` — это другие компании. `CONFIRMED` — все ссылки в документе ведут на `lightcast.io` / `docs.lightcast.io` / `docs.lightcast.dev` / `kb.lightcast.io` / `legal.lightcast.io`.

---

# Executive Summary

**Что такое Lightcast.** Крупнейший в мире поставщик labor market intelligence. Образован слиянием Emsi (economic modelling, госстатистика США) и Burning Glass Technologies (парсинг вакансий, skills-таксономия) в 2021. Владелец — private equity фонд **KKR** (`CONFIRMED` — [EDCC partnership deck, Nov 2022](https://edcconline.org/wp-content/uploads/2022/11/EDCC-Pricing-Updated-Lightcast.pdf)). Офисы: Boston + Moscow (Idaho), UK, Италия, Новая Зеландия, Индия. Модель — B2B-данные и SaaS для education / enterprise HR / госсектора.

**Ключевой вывод по Украине.** Сильные стороны Lightcast — **таксономии** (Skills, Titles, Occupations), **модели переходов** (Career Pathways, Similarity, Skill Gap) и **глубокие данные по США/UK/Канаде**. Всё это построено на данных США/UK/Канады и, во вторую очередь, крупных западных экономик. **Украина не входит ни в один "богатый" уровень покрытия.** Только США, UK и Канада относятся к Set 1 (`CONFIRMED` — [Global Sets, Lightcast KB](https://kb.lightcast.io/en/articles/13731693-global-sets)). Украины не было в списке из 41 страны до мартовской экспансии 2026 (`CONFIRMED` — [Global Data Release Notes](https://kb.lightcast.io/en/articles/9252367-global-data-release-notes) — Украина не упоминается вообще). После экспансии до 165+ стран (10 марта 2026, `CONFIRMED` — [PR Newswire](https://www.prnewswire.com/news-releases/lightcast-extends-global-data-footprint-by-300-delivering-the-industrys-largest-global-labor-market-coverage-302708689.html)) Украина, `INFERENCE`, попадает в **Set 3 или Set 4** — «basic visibility», вакансии только с сайтов работодателей (не с job-бордов), «sporadic or unreliable» агрегация (`CONFIRMED` — формулировки из Global Sets KB).

**Career Pathways API — только US / Canada / UK** (`CONFIRMED` — [Career Coach API suite](https://docs.lightcast.dev/guides/career-coach-api-suite), [Careers API](https://docs.lightcast.dev/apis/careers)). Для Украины его нет и в ближайшее время не будет. Но методология Career Pathways полностью документирована и **воспроизводима на ESCO + O*NET + собственных данных**.

**Рекомендация в одну строку:** **PILOT FIRST / HYBRID.** Брать у Lightcast то, что глобально и не зависит от страны (Skills-таксономия как справочник, опционально Classification API для извлечения навыков), а весь украинский слой — спрос, зарплаты, вакансии, украинские названия профессий, career pathways под Украину — строить самим на work.ua + robota.ua + ДСЗ + ESCO. Lightcast экономит нам **~4–7 месяцев** работы на таксономии и методологии переходов, но **не может быть единственным ядром** Career Transition Engine для Украины.

**Экономия времени разработки (оценка):** 4–7 месяцев (детально — §25 G).

---

# 1. Lightcast Data Architecture

`CONFIRMED` — Lightcast строит данные из трёх типов сырья ([Lightcast Data overview](https://lightcast.io/products/data/overview), [EDCC deck](https://edcconline.org/wp-content/uploads/2022/11/EDCC-Pricing-Updated-Lightcast.pdf)):

| Слой | Источник | Что даёт | Обновление |
|---|---|---|---|
| **Government / economic modelling** (наследие Emsi) | 100+ госисточников (в США: QCEW, OES/OEWS, BLS projections, IPEDS) + собственная межрегиональная social accounting matrix | Занятость, проекции на 10 лет, earnings, location quotient, shift-share, demographics, industry I/O | Ежеквартально (`CONFIRMED`) |
| **Job Postings Analytics / JPA** (наследие Burning Glass) | 220 000+ текущих и исторических источников: job-борды + сайты компаний; «advanced scraping» | Спрос: постинги по компании / городу / occupation / skills; advertised salary; posting intensity; ~13 навыков на постинг | Постинг → публикация ~36 часов; вся история переклассифицируется каждые 4 недели под новую таксономию (`CONFIRMED` — [JPA Methodology](https://kb.lightcast.io/en/articles/6957446-job-posting-analytics-jpa-methodology)) |
| **Profiles / Resumes** | Агрегированные онлайн-профили и резюме | 120M+ профилей в США: employer, job title, industry, alma mater, skill set; карьерные переходы; +100M+ дедуплицированных глобальных профилей после экспансии 2026 | Ежеквартально (`CONFIRMED`) |

Поверх сырья — **производные модели**: Skills Taxonomy, Occupation Taxonomy (LOT), Titles Taxonomy, Similarity Model, Career Pathways, Skill Gap model, DDN (Defining/Distinguishing/Necessary), Compensation/Role Pricing model, Projected Occupation/Skill Growth.

**Доставка клиенту (`CONFIRMED` — [docs.lightcast.io/data/docs](https://docs.lightcast.io/data/docs)):**
- **API** (`docs.lightcast.io/lightcast-api`, ранее `docs.lightcast.dev`) — REST, OAuth2 bearer, скоупы на каждый API.
- **Data Shares / bulk** — Amazon S3, Google BigQuery (+ Analytics Hub), GCS, Azure Blob, Snowflake (+ Marketplace), Databricks (+ Marketplace), SFTP.
- **Software** — Analyst / Talent Analyst / Developer / Career Coach (не наш путь — это UI, не данные).

`INFERENCE` — для нас релевантны только API и (возможно) Data Share для таксономий. Software-платформы не дают программного доступа к данным на нужном нам уровне.

---

# 2. Product / API Inventory

Формат: **Назначение → данные клиенту → доставка → гео → обновление → Ukraine → лицензия → применение в MNP.**

Полный список API — из [API menu](https://lightcast.io/our-data/api/menu) и [llms.txt индекса](https://docs.lightcast.io/lightcast-api/llms.txt) (`CONFIRMED`).

### 2.1 Таксономии и нормализация

**Open Skills / Skills Taxonomy**
- Назначение: стандартный справочник навыков.
- Данные: 34 000+ навыков; 3 типа (Specialized / Common / Certifications); 31 категория, 400+ подкатегорий; machine-readable skill IDs; aliases; описания; changelog (`CONFIRMED` — [Open Skills Taxonomy blog](https://lightcast.io/resources/blog/open-skills-taxonomy), [our-taxonomies](https://lightcast.io/products/data/our-taxonomies)).
- Доставка: просмотр/выгрузка онлайн бесплатно; **API — «на контрактной основе»** (`CONFIRMED` — [Open Skills FAQ](https://lightcast.io/open-skills/faqs): *"API access is now available on a contract basis"*); также BigQuery Analytics Hub (open taxonomies).
- Гео: страна-агностична (навыки не привязаны к стране).
- Обновление: ежемесячно (новая версия библиотеки) (`CONFIRMED`).
- Ukraine: N/A (навыки глобальны); **но украиноязычные aliases — `UNKNOWN`** (см. §4).
- Лицензия: Open Terms of Use — royalty-free, perpetual, non-transferable, non-sublicensable; **по умолчанию только non-commercial**; коммерческое использование — по письменному контракту; **обязательная атрибуция** + ссылка на лицензию (`CONFIRMED` — [Open Terms of Use v1.2](https://legal.lightcast.io/lightcast-legal/open-terms-of-use?v=1.2)).
- Применение в MNP: справочник навыков; кандидат на mapping-слой (§6).

**Titles Taxonomy / Open Titles**
- 75 000+ нормализованных должностей, machine-readable IDs, из миллионов сырых заголовков (`CONFIRMED` — [our-taxonomies](https://lightcast.io/products/data/our-taxonomies)).
- Кросс-уок на Occupations. Обновление — не указано. Ukraine — украинские заголовки `UNKNOWN` / `INFERENCE` не покрыты (таксономия строилась на англоязычных постингах).
- Применение в MNP: нормализация job titles из CV → но для украинских CV потребуется свой слой.

**Occupation Taxonomy (LOT — Lightcast Occupation Taxonomy)**
- 1800+ specialized occupations; 4-уровневая иерархия: career areas → occupation groups → occupations → specialized occupations; crosswalk на **O*NET, SOC, ISCO** (`CONFIRMED` — [our-taxonomies](https://lightcast.io/products/data/our-taxonomies), [LOT v7 update](https://kb.lightcast.io/en/articles/10430137-lightcast-occupation-taxonomy-update)).
- Версии: v7 с апреля 2025, дефолт во всех продуктах; годовой цикл; 92% концептов стабильны между v6→v7 (`CONFIRMED`).
- «Global Occupation Taxonomy» — при экспансии 2026 гео/occupation-таксономии выровнены под локальные госопределения для кросс-странового сравнения (`CONFIRMED` — [footprint +300% blog](https://lightcast.io/resources/blog/lightcast-extends-global-data-footprint-by-300percent)). ISCO-кросс-уок = мост к украинскому КП (Класифікатор професій, основан на ISCO-08).
- Ukraine: сама таксономия применима через ISCO; **украинские данные по профессиям — см. §3, §9.**
- Лицензия: часть «Open» линейки; коммерческое — контракт.
- Применение в MNP: скелет Career Knowledge Base; мост MNP Career ID ↔ ISCO ↔ КП України.

**Classification API / Classification 2.0**
- Назначение: парсинг текста и маппинг на таксономии; извлечение навыков из текста; нормализация titles; маппинг между версиями таксономий.
- Эндпоинты: `/taxonomies`, `/mappings`, `/classifications` (`CONFIRMED` — [Classification overview](https://docs.lightcast.io/lightcast-api/reference/overview-classification)).
- Скоупы: `classification_api` или `lightcast_open`. Rate limit: 5 req/s по умолчанию.
- Таксономии: skills, titles, companies (SOC/O*NET/ESCO/NOC — `UNKNOWN`, не перечислены явно в overview).
- **Языки, в т.ч. украинский — `UNKNOWN` / `MUST ASK LIGHTCAST`** (документация overview молчит).
- Ukraine: N/A по гео; вопрос — язык.
- Применение в MNP: извлечение навыков из англоязычной части CV; skill-extraction как замена собственному NER.

### 2.2 Спрос / вакансии

**Job Postings US** / **Job Postings Global** / **UK Postings** / **Canada Postings** / **Company Direct**
- Данные: агрегаты по постингам — occupation, skills, certifications, title, company, city, education level, industry; advertised salary (только объявленная, не моделированная); posting intensity (total/dedup ratio); timeseries; distributions; ranked facets; nested rankings (`CONFIRMED` — [JPA](https://kb.lightcast.io/en/articles/6957446-job-posting-analytics-jpa-methodology), [EDCC deck p.8](https://edcconline.org/wp-content/uploads/2022/11/EDCC-Pricing-Updated-Lightcast.pdf)).
- Дедупликация: убирается ~80% дублей (`CONFIRMED`).
- Гео: 165+ стран, но глубина = Set страны.
- История: США — постинги с ~2007; глобально — зависит от Set (Set 1 — 10+ лет; Set 4 — минимальная) (`CONFIRMED` — Global Sets).
- Обновление: постинг→публикация ~36 ч; агрегаты ежемесячно/ежедневно в зависимости от продукта.
- **Ukraine: `INFERENCE` Set 3/4 — вакансии только с корпоративных сайтов, без work.ua/robota.ua/OLX; «sporadic or unreliable»; salary-поле почти пустое.** `MUST ASK LIGHTCAST` — точный Set Украины, объём постингов/мес, доля с зарплатой, глубина истории.
- Лицензия: платно, контракт. Хранение/кэш — см. §13.
- Применение в MNP: **низкое для Украины.** Для украинского спроса — work.ua/robota.ua/ДСЗ.

**Projected Occupation Growth** / **Projected Skill Growth**
- Прогноз роста профессий и навыков (skill growth — горизонт 2 года) (`CONFIRMED` — [API menu](https://lightcast.io/our-data/api/menu)).
- Гео: `UNKNOWN`, `INFERENCE` — США (наследие Emsi projections), возможно Set 1/2.
- Ukraine: `INFERENCE` — нет.
- Применение в MNP: «растущая/падающая профессия» — только как глобальный сигнал, не украинский.

### 2.3 Переходы и матчинг (наиболее ценное — и наиболее US-центричное)

**Career Pathways API**
- Назначение: next-step и feeder occupations для выбранной профессии + навыки для перехода + skill-gap score.
- 4 категории переходов: Advancement, Lateral Advancement, Similar, Lateral Transition (детально — §7).
- Relevance Score по каждой destination; Importance Score по каждому transitional skill.
- Таксономии: LOT + O*NET-SOC, specialized и general уровни.
- **Гео: US, Canada, UK — CONFIRMED** ([Career Coach API suite](https://docs.lightcast.dev/guides/career-coach-api-suite), [Careers API](https://docs.lightcast.dev/apis/careers)). Pathways «применяются across geographies within a country» (`CONFIRMED` — [Career Pathways data](https://docs.lightcast.io/data/docs/career-pathways)) — т.е. внутри страны не регионализированы, но и **не выходят за пределы US/CA/UK**.
- Ukraine: **не доступно.** `INFERENCE` — и не появится в среднесроке (нужны глубокие постинги + профили Украины).
- Применение в MNP: **как референс-методология, не как API.** Воспроизводим на ESCO+O*NET.

**Similarity API / Similarity Model**
- Меряет близость occupation↔occupation, skill↔occupation, occupation↔skill; score 0..1 (1 = очень похоже); уровни 5-digit SOC, O*NET, specialized; обновление ежеквартально; питает Career Pathways, DDN, «Similar Occupations», Talent Supply by Compensation (`CONFIRMED` — [Similarity Model KB](https://kb.lightcast.io/en/articles/12101614-lightcast-similarity-model)).
- Гео: `INFERENCE` — построена на постингах US (+ возможно UK/CA). Ukraine — нет.
- Применение в MNP: методология «skill-based occupation similarity» воспроизводима на ESCO skill-векторах.

**DDN (Defining / Distinguishing / Necessary) Skills**
- Классифицирует навыки профессии по уровню значимости для роли (`CONFIRMED` — [API menu](https://lightcast.io/our-data/api/menu), Similarity KB).
- Применение в MNP: аналог нашего «какие навыки определяют профессию X» — критично для Skill Gap. Воспроизводимо на частотах ESCO/O*NET + постингов work.ua.

**Similarity / Salary-Boosting Skills / Skill premium**
- «Salary-Boosting Skills» — навыки, коррелирующие с более высокой оплатой (`CONFIRMED` — [API menu](https://lightcast.io/our-data/api/menu)).
- Гео/методология конкретно — `UNKNOWN`; `INFERENCE` — US postings с зарплатой.
- Ukraine: нет (нужны украинские постинги с зарплатой → work.ua/robota.ua).

**Occupation Benchmark** / **Talent Benchmark**
- Occupation Benchmark: гранулярность ниже SOC, «12-month landscape», навыки/работодатели/спрос; rate limit 5 req/s (`CONFIRMED` — [role-pricing/limits](https://docs.lightcast.dev/apis)).
- Talent Benchmark: один вызов = supply + demand + compensation + diversity + skills.
- Гео: `INFERENCE` US (+Set1/2). Ukraine — нет.

### 2.4 Зарплаты

**Compensation API** / **Market Salary API** / **Role Pricing API**
- Compensation/Role Pricing: моделированная вилка зарплаты по region + skills + experience + education; модель обучена на постингах + occupational earnings (`CONFIRMED` — [Role Pricing](https://docs.lightcast.dev/apis/role-pricing)).
- Market Salary: зарплата по occupation + рынку; rate limit — unlimited по умолчанию.
- Гео: `INFERENCE` — США надёжно (40M+ compensation observations, привязка к OES); прочие страны = зависит от объёма постингов с зарплатой.
- **Ukraine: `INFERENCE` — модель отдаст число, но качество низкое (мало постингов с advertised salary).** `MUST ASK LIGHTCAST`.
- Применение в MNP: для Украины — work.ua/robota.ua медианы; Lightcast — только как «глобальный ориентир для профессии».

### 2.5 Профили / люди

**Profiles (Anonymized)** / **Global Profiles** / **Profiles with Contact Info**
- Агрегаты по работникам: employer, occupation (SOC/O*NET), skills, industry, region, alma mater; карьерные переходы (кто откуда куда двигался) (`CONFIRMED` — [EDCC deck p.9](https://edcconline.org/wp-content/uploads/2022/11/EDCC-Pricing-Updated-Lightcast.pdf)).
- «Profiles with Contact Info» — с верифицированными контактами (наследие Rhetorik) — для рекрутинга; **для B2C-продукта юридически чувствительно, не наш кейс.**
- Гео: 120M+ США; +100M+ глобально после 2026; рост в CA/UK/US, добавлены Китай/Япония/Корея (`CONFIRMED`).
- **Ukraine: `UNKNOWN` — вероятно тонко.** `MUST ASK LIGHTCAST`.
- Применение в MNP: реальные карьерные переходы = золото для Transition Engine, **но по Украине почти наверняка нет объёма.**

### 2.6 Ассессмент

**Assessments API (Career Coach)**
- RIASEC / Holland Occupational Themes; отдаёт traits и наборы вопросов; скорит и хранит завершённые ассессменты; матчит на 16 career categories (`CONFIRMED` — [Career Coach API suite](https://docs.lightcast.dev/guides/career-coach-api-suite)).
- Гео: привязан к Career Coach → US/CA/UK.
- Ukraine: нет; и это **не то, что нужно MNP** (MNP — не тест типа личности, а перенос career capital — см. §16 контекста продукта).
- Применение в MNP: **не использовать.** Наш ассессмент — про опыт/навыки/ограничения, не про RIASEC.

### 2.7 Прочее (низкая релевантность для MNP V1)

| API | Что | Релевантность MNP |
|---|---|---|
| Core LMI / Agnitio | Госстат США: industries/occupations/geographies/demographics, проекции; rate 300/5min; **не упоминает non-US** (`CONFIRMED` — [Core LMI overview](https://docs.lightcast.io/lightcast-api/reference/overview-core-lmi)) | Низкая (US only) |
| IPEDS / Completers | Данные о выпускниках вузов США, CIP↔SOC | Нет (US education) |
| Curricular Skills / Programs & Profiles | Навыки курсов/программ для вузов | Нет в V1 |
| GIS | Геоанализ: радиус, время в пути, GeoJSON | Возможно позже (карта вакансий) |
| Cost of Living | Индексы стоимости жизни (US) | Нет |
| Companies / Classification of companies | Нормализация названий компаний | Низкая |
| Alumni Pathways 2.0 | Карьерные траектории выпускников по когортам | Нет в V1 |

---

# 3. Ukraine Coverage Matrix

**Метод:** проверяем каждый датасет отдельно. Base rate: только **US, UK, Canada = Set 1** (`CONFIRMED` — [Global Sets](https://kb.lightcast.io/en/articles/13731693-global-sets)). Украина отсутствует в списке 41 страны из [Global Data Release Notes](https://kb.lightcast.io/en/articles/9252367-global-data-release-notes) (`CONFIRMED`), т.е. добавлена только в экспансии 10 марта 2026 → `INFERENCE` **Set 3 или Set 4**.

**Определения Set (`CONFIRMED` — [Global Sets KB](https://kb.lightcast.io/en/articles/13731693-global-sets), [global-data](https://lightcast.io/products/data/global-data)):**
- **Set 1** (US/UK/CA): полный demand+supply, workforce estimates, compensation, demographics, 10+ лет истории.
- **Set 2** (AU, AT, BE, FR, DE, IE, IT, ...): сильное покрытие, multi-year demand, worker estimates, salary.
- **Set 3**: «core job postings, information on leading employers, and primary LMI».
- **Set 4**: «basic-level coverage for core jobs, skills, and occupations»; **постинги только с сайтов компаний, не с job-бордов/посредников**; агрегация «sporadic or unreliable»; доступно через API и Data Share для «early-stage or directional analysis».

| Data / API | Ukraine | Depth | Freshness | Suitable for MNP? | Limitations |
|---|---|---|---|---|---|
| Job postings (current) | `INFERENCE` Set 3/4 | Очень мелко; только корп-сайты | Ежемесячно | ❌ Нет | Без work.ua/robota.ua/OLX; малый объём; нестабильно |
| Historical job postings | `INFERENCE` минимально | Короткая история | — | ❌ Нет | Не хватит для динамики 12 мес |
| Advertised salary | `INFERENCE` почти пусто | — | — | ❌ Нет | Мало постингов с зарплатой в UA |
| Modeled compensation | `INFERENCE` отдаст число | Низкое качество для UA | Ежеквартально | ⚠️ Только как ориентир | Модель на тонких данных |
| Profiles / transitions | `UNKNOWN` | `UNKNOWN`, вероятно тонко | Ежеквартально | ⚠️ `MUST ASK` | Нужен объём для statistically-sound переходов |
| Occupations (таксономия) | ✅ применима через ISCO | Полная | v7, годовой цикл | ✅ Да (как скелет) | Нужен UA-слой названий |
| Skills (таксономия) | ✅ применима | Полная | Ежемесячно | ✅ Да (как справочник) | UA aliases `UNKNOWN` |
| Titles | ⚠️ англ. заголовки | — | — | ⚠️ Частично | Украинские заголовки не покрыты |
| Employers | `INFERENCE` частично (крупные) | Мелко | — | ❌ Нет | Только большие компании с англ-сайтами |
| Locations | ✅ админ-области UA есть | Область/город | — | ⚠️ Да для геопривязки | Гранулярность ниже, чем в UA-бордах |
| Education requirements | `INFERENCE` из глобальных постингов | Не UA-специфично | — | ❌ Для UA нет | UA-специфика (диплом/ОКР) не отражена |
| Experience requirements | `INFERENCE` из глобальных постингов | Не UA-специфично | — | ❌ Для UA нет | — |
| Certifications | ⚠️ глобальный список | Не UA | Ежемесячно | ⚠️ Частично | UA/EU сертификации, ДСЗ-курсы — нет |
| Career pathways | ❌ **Не доступно** | — | — | ❌ Нет | API только US/CA/UK |
| Skill gaps (между профессиями) | ❌ (часть Career Pathways) | — | — | ❌ Нет | Методология воспроизводима |
| Transition scores | ❌ | — | — | ❌ Нет | — |
| Demand / historical demand | `INFERENCE` Set 3/4 | Ненадёжно | Ежемесячно | ❌ Нет | См. job postings |
| Emerging / declining skills | `INFERENCE` глобально/Set1 | Не UA | 2-year proj | ⚠️ Глобальный сигнал | Не украинский тренд |
| Skill premiums | ❌ для UA | — | — | ❌ Нет | Нужны UA-постинги с зарплатой |
| Workforce estimates (WEMo) | `INFERENCE` Set 3+ есть, грубо | Страна/регион | Периодически | ⚠️ Только макро | Не по профессиям детально |

**Вывод §3 (`INFERENCE`):** для Украины Lightcast полезен как **страна-агностичный слой** (Skills/Occupations таксономии, методологии, глобальные бенчмарки). **Всё, что "labour market intelligence по Украине" (спрос, зарплаты, вакансии, работодатели, тренды) — Lightcast закрывает плохо или никак.** Это не дефект Lightcast — это структурное следствие того, что рынок труда Украины живёт на украиноязычных job-бордах, которые Lightcast для Set 3/4 стран не парсит.

---

# 4. Украинский язык — отдельно

| Вопрос | Ответ | Маркер |
|---|---|---|
| Распознаёт ли Lightcast украинские названия профессий? | Не подтверждено. JPA обрабатывает не-английские постинги «без перевода», но названные языки (Feb 2024): EN, ES, DE, FR, NL, IT, PT, PL, DA — **украинского нет** ([PR](https://www.prnewswire.com/news-releases/lightcast-unleashes-the-most-comprehensive-global-labor-data-used-by-talent-and-business-leaders-302060291.html)). Позже заявлено «17 languages» / «linguistic expertise, not machine translation» ([global-data](https://lightcast.io/products/data/global-data)), но состав 17 языков не опубликован. | `UNKNOWN` / `MUST ASK LIGHTCAST` |
| Украинские skills (украиноязычные названия навыков) | Таксономия ведётся на английском; украинские aliases не подтверждены | `UNKNOWN` / `MUST ASK` |
| Украинские CV (парсинг) | Classification API языковую поддержку не документирует | `UNKNOWN` / `MUST ASK` |
| Украинские job descriptions | См. языки JPA выше | `INFERENCE` — не поддерживается на уровне Set 1/2 |
| Mixed UA/EN CV | — | `UNKNOWN` |
| Локализация таксономии | Occupation/geo выровнены под локальные госопределения при экспансии 2026; про язык интерфейса таксономии — молчание | `UNKNOWN` |
| Нужен ли нам свой UA aliases / translation layer? | **Да, почти наверняка.** | `INFERENCE` (высокая уверенность) |

**Вывод §4:** планируем **собственный украинский лексический слой**: UA-названия профессий (из КП України + work.ua/robota.ua), UA-синонимы навыков, UA→EN нормализацию (LLM + словарь) перед любым обращением к Lightcast. Даже если Lightcast скажет «украинский поддерживается» — на Set 3/4 качество будет ниже, чем наш кураторский слой.

---

# 5. Occupation / Career Taxonomy

**Что подтверждено (`CONFIRMED`):**
- LOT v7 (апрель 2025): 1800+ specialized occupations, 4 уровня (career area → occupation group → occupation → specialized occupation), кросс-уок на **O*NET, SOC, ISCO** ([LOT v7](https://kb.lightcast.io/en/articles/10430137-lightcast-occupation-taxonomy-update), [our-taxonomies](https://lightcast.io/products/data/our-taxonomies)).
- Годовой цикл обновления, высокая межверсионная стабильность (92%).
- Occupation ↔ skills, occupation ↔ education/experience (6 tiers для LOT / 5 job zones для O*NET), occupation ↔ salary, occupation ↔ postings — всё есть **для US** (`CONFIRMED` — [Career Pathways data](https://docs.lightcast.io/data/docs/career-pathways), [EDCC deck](https://edcconline.org/wp-content/uploads/2022/11/EDCC-Pricing-Updated-Lightcast.pdf)).

**Можно ли использовать Lightcast как master Career KB?**
- **Нет — как единственный master.** `INFERENCE`. Причины: (1) украинские названия/специфика не покрыты; (2) LOT оптимизирован под рынок США; (3) vendor lock-in на структуру, которую мы не контролируем; (4) годовые изменения LOT ломали бы нашу KB.
- **Да — как один из источников скелета.** LOT + его ISCO-кросс-уок = хороший каркас верхнего уровня.

**Рекомендуемая архитектура Career KB (`INFERENCE`):**
```
MNP Career ID (наш, стабильный, версионируемый)
   ├── ↔ ISCO-08  (мост, международный стандарт, основа КП України)
   ├── ↔ КП України / ДК 003:2010  (официальные украинские коды)
   ├── ↔ ESCO occupation URI  (открытый, европейский, 3000+ профессий, многоязычный вкл. потенциально UA)
   ├── ↔ O*NET-SOC  (для skills/abilities/work context — богатейший открытый источник признаков профессии)
   ├── ↔ Lightcast LOT ID  (опционально, если купим — для similarity/pathways-референса)
   ├── ← work.ua occupation/category  (украинский спрос)
   └── ← robota.ua rubric  (украинский спрос)
```
MNP Career ID — единственный ID, на который завязана продуктовая логика. Все остальные — mappings в отдельной таблице, каждый может отвалиться без поломки ядра.

---

# 6. Skills Taxonomy

**Подтверждено (`CONFIRMED` — [Open Skills Taxonomy blog](https://lightcast.io/resources/blog/open-skills-taxonomy), [our-taxonomies](https://lightcast.io/products/data/our-taxonomies), [Open Skills FAQ](https://lightcast.io/open-skills/faqs)):**

| Свойство | Значение |
|---|---|
| Кол-во | 34 000–35 000+ навыков |
| Типы | Specialized (hard), Common (soft/human), Certifications |
| Иерархия | 31 категория → 400+ подкатегорий → навыки |
| Skill IDs | Есть, machine-readable, стабильные |
| Aliases | Есть (англ.) |
| Relationships | skill↔skill через Similarity Model; skill↔occupation через Similarity + DDN |
| skill↔salary | «Salary-Boosting Skills» (US postings) |
| skill↔demand | Через JPA (US + Set 1/2) |
| Обновление | Ежемесячно, публичный changelog |
| Доступ | Просмотр/выгрузка онлайн бесплатно; API — контракт; BigQuery Analytics Hub |
| Языки | EN основной; прочие — `UNKNOWN` |
| Crosswalk | На O*NET / ISCO упоминается для occupations; **skill-level crosswalk на ESCO — `UNKNOWN`, официально не заявлен Lightcast** |

**Сравнение с ESCO и O*NET:**

| Критерий | Lightcast Skills | ESCO (v1.2) | O*NET |
|---|---|---|---|
| Владелец | Lightcast (частный) | Еврокомиссия (публичный) | Минтруда США (публичный) |
| Лицензия | Open Terms (non-commercial по умолчанию, commercial — контракт) | Открытая, коммерческое использование разрешено | Открытая (public domain-подобная) |
| Кол-во навыков | 34k+ | ~13 900 skills/competences | ~35 элементов Skills + сотни work activities/knowledge |
| Языки | EN (+?) | **27 языков ЕС** (украинского нет в офиц., но структура переводимая) | EN (+ испанский) |
| Гранулярность | Очень высокая (рыночная, «AWS», «Kubernetes») | Высокая, но более академичная | Низкая по «skills», высокая по knowledge/activities |
| Обновление | Ежемесячно (рыночное) | Редко (годы) | ~Ежегодно |
| Свежесть emerging skills | Отличная | Слабая | Слабая |
| Риск lock-in | **Высокий** | Нет | Нет |

**Архитектурная рекомендация (`INFERENCE`, высокая уверенность):**

> **НЕ использовать Lightcast skill_id как основной идентификатор навыков в MNP.**
>
> Ввести **MNP Skill ID** (собственный, стабильный) + таблицу mappings:
> `MNP Skill ID ↔ ESCO ↔ O*NET ↔ (Lightcast, опционально) ↔ UA-синонимы`
>
> Базовый справочник строить на **ESCO** (открытый, многоязычный, коммерчески-дружелюбный, есть структура для украинской локализации) + дополнять **Lightcast-навыками для tech/digital** (там, где ESCO отстаёт от рынка) — если и когда будет контракт.

Причина: Lightcast Open Terms по умолчанию non-commercial, API стал контрактным, таксономия меняется ежемесячно, ID непереносимы. Строить на этом ядро коммерческого продукта = стратегический риск (§24).

---

# 7. Career Pathways — Reverse Engineering

**Как Lightcast строит Occupation A → Occupation B (`CONFIRMED` — [Career Pathways KB](https://kb.lightcast.io/en/articles/6641056-lightcast-career-pathways), [Career Pathways data](https://docs.lightcast.io/data/docs/career-pathways), [Similarity Model](https://kb.lightcast.io/en/articles/12101614-lightcast-similarity-model)):**

1. **Similarity Model** (ядро): по миллионам постингов строит skill-профиль каждой профессии → считает occupation-occupation similarity 0..1 на основе пересечения требований по навыкам. Обновляется ежеквартально.
2. **Дополнительные факторы отбора переходов:**
   - Education / experience requirement levels (6 tiers для LOT; 5 job zones для O*NET).
   - Advertised salary данные (для классификации «платит больше / сопоставимо»).
   - Licensing и specialized training requirements.
   - Taxonomic hierarchy (тот же occupation group или другой).
3. **Next-step vs Feeder:** next-step — куда работники переходят из фокусной профессии; feeder — откуда приходят в неё. Строится на фактических переходах из **профилей** + на similarity.
4. **4 категории перехода:**

| Категория | Оплата | Occupation group |
|---|---|---|
| **Advancement** | Выше | Тот же |
| **Lateral Advancement** | Выше | Другой |
| **Similar** | Сопоставимая | Тот же |
| **Lateral Transition** | Сопоставимая | Другой |

5. **Скоринг:** каждая destination получает **Relevance Score** (по skills alignment). Каждый transitional skill — **Importance Score** (детали — §8).

**Что возвращает API (`CONFIRMED` частично; полная схема — `UNKNOWN`, docs.lightcast.dev рендерится JS и не читается публично без ключа):**
- Список next-step / feeder occupations для заданного occupation ID.
- Категория перехода (4 типа).
- Relevance / similarity score.
- Список навыков для перехода + importance score каждого.
- Фильтры: по occupation ID и по типу категории.

**Пример request/response JSON:** `UNKNOWN` — публичная документация Career Pathways API (`docs.lightcast.dev/apis/career-pathways`) отдаётся как JS-SPA и не индексируется; Postman-коллекция Lightcast Public требует авторизации для полноты. `MUST ASK LIGHTCAST` — запросить реальные примеры request/response или доступ к sandbox.

**Можно ли использовать Career Pathways как основу нашего Career Transition Engine?**
- **Как API — нет** (US/CA/UK only, Украины нет).
- **Как методологию — да, полностью.** Она документирована достаточно, чтобы воспроизвести:
  - skill-vector каждой профессии → из ESCO occupation-skill relations + O*NET + постингов work.ua/robota.ua;
  - occupation-occupation similarity → cosine на skill-векторах (взвешенных по importance);
  - education/experience gap → из ESCO/O*NET job zones + украинских требований в вакансиях;
  - salary direction → из медиан work.ua/robota.ua;
  - 4 категории → та же логика (Δsalary × same/different group).
- **Вывод:** Career Transition Engine — это **BUILD (наш IP)**, с Lightcast Career Pathways как эталоном для валидации на US-кейсах (если купим доступ на короткий срок для калибровки).

---

# 8. Skill Gap Engine

**Методология Lightcast (`CONFIRMED` — [Career Pathways data](https://docs.lightcast.io/data/docs/career-pathways), [Career Pathways KB](https://kb.lightcast.io/en/articles/6641056-lightcast-career-pathways)):**

- **Что такое gap:** навыки, где destination-профессия требует бóльшего уровня/частоты, чем source-профессия. Т.е. это разница skill-профилей двух профессий, **не** разница «человек vs профессия» напрямую (см. ниже).
- **Defining skills:** через модель DDN (Defining / Distinguishing / Necessary) — какие навыки определяют профессию.
- **Importance / ранжирование gap:** Importance Score считается из **двух факторов**: (1) величина разрыва по навыку между профессиями; (2) корреляция навыка с зарплатой. → ранжированный список «самых полезных к освоению» навыков.
- **Frequency:** да, участвует (частота навыка в постингах профессии).
- **Salary value:** да, участвует (корреляция с зарплатой).
- **Direction-specific:** да — gap считается направленно (A→B ≠ B→A).
- **API возвращает score:** да (Importance Score по каждому навыку).
- **Existing + missing skills:** Lightcast отдаёт skill-профили обеих профессий и transitional skills; «existing» — это пересечение, «missing» — то, что нужно добрать.

**Гипотеза Founder: «Які 3–5 навичок тобі найвигідніше вивчити, щоб перейти в професію X і збільшити дохід?»**

Разложение:

| Компонент функции | Кто считает |
|---|---|
| Skill-профиль текущей профессии | Lightcast (US) / **MNP** (UA, на ESCO+work.ua) |
| Skill-профиль целевой профессии X | Lightcast (US) / **MNP** (UA) |
| Разница профилей (gap) | Lightcast формула / **MNP** (та же формула) |
| Какие навыки defining для X | Lightcast DDN / **MNP** (частоты + DDN-логика) |
| Корреляция навыка с зарплатой | Lightcast (US postings) / **MNP** (work.ua/robota.ua постинги с зарплатой) |
| **Персонализация: что уже есть у ЭТОГО человека** | ❌ **Lightcast не делает** — он работает occupation→occupation, не person→occupation. **Это MNP.** |
| Ранжирование «топ-5 самых выгодных» | Lightcast Importance Score / **MNP** (gap × salary_value × learnability × UA-demand) |
| «Увеличить доход» — на сколько именно в Украине | ❌ **Lightcast для UA не знает.** **MNP** на украинских зарплатах. |
| Время/стоимость обучения навыку | ❌ Lightcast не даёт. **MNP** (каталог обучения) |

**Что реально считает Lightcast:** occupation-to-occupation skill gap + importance (gap-size + salary-correlation), для US/CA/UK.

**Что считаем мы:** (1) person-to-occupation gap (учёт того, что человек уже умеет — из Career Card); (2) весь украинский слой — какие навыки в дефиците в UA, какая прибавка к доходу в UA, что доступно выучить; (3) learnability/время; (4) финальное ранжирование под конкретного пользователя и его ограничения.

**Вывод §8:** Skill Gap Engine = **HYBRID с сильным перевесом в BUILD.** Формула и структура — от Lightcast (открыто описаны). Данные для Украины и вся персонализация — наши. Функцию «3–5 навичок» **можно построить**, но Lightcast закрывает в ней максимум ~30% (методология + глобальный salary-signal), а 70% — наш код + украинские данные.

---

# 9. Labour Market Intelligence (Украина)

Хотим показывать на карточке профессии:

```
Data Analyst (Україна)
Вакансій зараз: X
Зміна за 12 міс.: +Y%
Медіанна зарплата: Z грн
TOP навички: ...
Emerging навички: ...
TOP регіони: ...
Поріг входу: ...
```

| Поле | Может ли дать Lightcast для Украины | Маркер |
|---|---|---|
| Вакансій зараз | Технически да (Set 3/4), но заниженное число (только корп-сайты) | `INFERENCE` — непригодно |
| Зміна за 12 міс. | Нужна история → в Set 3/4 её мало | `INFERENCE` — непригодно |
| Медіанна зарплата | Modeled compensation отдаст число, качество низкое; advertised salary — почти пусто | `INFERENCE` — непригодно как основной источник |
| TOP навички профессии | Да — но из глобального/US skill-профиля, не из украинских вакансий | `INFERENCE` — как прокси допустимо |
| Emerging навички | Глобальный Projected Skill Growth (2 года) — не украинский | `INFERENCE` — только глобальный сигнал |
| TOP регіони | Слабо (мало постингов) | `INFERENCE` — непригодно |
| Поріг входу (education/experience) | Из глобальных постингов профессии — не украинская специфика | `INFERENCE` — как прокси |
| Remote/hybrid | Из постингов — для UA мало | `INFERENCE` — непригодно |

**Вывод §9:** практически весь блок «Ukraine Labour Market Intelligence» Lightcast **не закрывает**. Источник — **work.ua + robota.ua (+ OLX Робота, dou.ua для IT) + ДСЗ**. Lightcast может дать только «эталонный skill-профиль профессии» как прокси, когда украинских постингов по нише мало.

---

# 10. Salary & Economic Data

- **США:** сильно. 40M+ compensation observations, привязка к OES/OEWS, percentiles, cost-of-living adjusted (`CONFIRMED` — [EDCC deck](https://edcconline.org/wp-content/uploads/2022/11/EDCC-Pricing-Updated-Lightcast.pdf)).
- **Advertised salary:** Lightcast извлекает только объявленную зарплату, не «estimated», конвертирует часовые в годовые по страновым нормам, курсы валют раз в ~4 недели (`CONFIRMED` — [JPA Methodology](https://kb.lightcast.io/en/articles/6957446-job-posting-analytics-jpa-methodology)).
- **Modeled salary (Role Pricing / Compensation API):** region + skills + experience + education (`CONFIRMED` — [Role Pricing](https://docs.lightcast.dev/apis/role-pricing)).
- **Украина:** `INFERENCE` — модель формально работает, но обучена на тонких данных → доверия низкое. `MUST ASK LIGHTCAST` — покрывает ли Role Pricing/Compensation Украину и с какой методологией/погрешностью.
- **Skill premium / Salary-Boosting Skills:** US postings. Для UA — нет.

**Вывод §10:** зарплаты по Украине — **BUILD** на work.ua/robota.ua медианах (у обоих бордов есть зарплатная аналитика и опубликованные обзоры). Lightcast — только «международный контекст профессии» (напр. «Data Analyst в ЕС получает €X» как мотивационный ориентир для тех, кто рассматривает выезд/возврат).

---

# 11. Ukraine Hybrid Data Stack

**Рекомендуемая архитектура (`INFERENCE`):**

```
┌─────────────────────────────────────────────────────────────────┐
│                     MNP CAREER INTELLIGENCE ENGINE               │
│  (детерминированное ядро; LLM только для parsing/explanations)   │
└─────────────────────────────────────────────────────────────────┘
        ▲                    ▲                     ▲
        │                    │                     │
┌───────┴────────┐  ┌────────┴─────────┐  ┌───────┴──────────┐
│ TAXONOMY LAYER │  │  DEMAND LAYER    │  │  KNOWLEDGE LAYER │
│ (страна-агност)│  │  (Україна)       │  │  (профессии)     │
├────────────────┤  ├──────────────────┤  ├──────────────────┤
│ ESCO (ядро)    │  │ work.ua          │  │ O*NET (признаки  │
│ O*NET (признаки)│  │ robota.ua        │  │  профессий)      │
│ Lightcast Skills│  │ OLX Робота       │  │ ESCO occupations │
│  (tech/digital, │  │ dou.ua (IT)      │  │ MNP curated KB   │
│   ОПЦИОНАЛЬНО)  │  │ ДСЗ (офиц.       │  │  (§14 doc: не    │
│ КП України/ISCO │  │  вакансії,       │  │   full graph,    │
│ MNP Skill/Career│  │  дефіцитні       │  │   а куратор.)    │
│  ID + mappings  │  │  професії,       │  │                  │
│                 │  │  навчання)       │  │                  │
└────────────────┘  └──────────────────┘  └──────────────────┘

MNP CALCULATION LAYER (наш IP):
  • Career Card (CV → структура)
  • Transferable skills (person → skills)
  • Occupation similarity (skill-vector cosine, методология Lightcast)
  • Transition scoring (feasibility под Украину + ограничения пользователя)
  • Skill Gap (person → target occupation, направленно)
  • Income upside (украинские зарплаты)
  • Opportunity matching (реальные вакансии work.ua/robota.ua/ДСЗ)
```

**Роли:**
- **Lightcast** → (опционально, при контракте) tech/digital навыки, которых нет в ESCO; референс-методология Similarity/Pathways/DDN; глобальные бенчмарки для персон «выезд/возврат». **Не критический путь.**
- **ESCO** → открытое многоязычное ядро таксономии навыков и профессий; occupation-skill relations; коммерчески-дружелюбная лицензия.
- **O*NET** → богатейший открытый источник признаков профессий (abilities, work activities, work context, job zones) для feasibility и similarity.
- **work.ua / robota.ua** → украинский спрос, зарплаты, украинские названия должностей, работодатели, региональная разбивка. **Способ доступа — `MUST CLARIFY`** (официальный API / партнёрство / договорный парсинг — отдельная задача DATA-002).
- **ДСЗ (Державна служба зайнятості)** → официальные вакансии, перечень дефіцитних професій, государственные программы переобучения, ваучеры. Открытые данные + портал.
- **MNP** → Career Card, feasibility под Украину, ограничения и предпочтения пользователя, скоринг переходов, income upside, матчинг возможностей, объяснения.

**Почему не «Lightcast + всё остальное вторично»:** потому что для целевой аудитории MNP (украинцы, ищущие/сменившие работу в Украине) **решающие данные — украинские**, а их у Lightcast нет. Lightcast был бы ядром, если бы мы делали продукт для рынка США.

---

# 12. API Architecture for MNP

**Принципы (соответствуют [14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md](14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md) — детерминированное ядро, LLM не на каждом шаге):**

1. **Anti-corruption layer.** Ни один внешний ID (Lightcast/ESCO/O*NET) не проникает в доменную модель. Только `MNP Skill ID` / `MNP Career ID`. Внешние источники — за адаптерами.
2. **Кэш + снапшоты.** Любой ответ внешнего API кладётся в наш store с версией и датой. Ядро читает из нашего store, не из внешнего API в реальном времени. (Юридическая допустимость постоянного хранения — §13, `MUST ASK`.)
3. **Оффлайн-построение.** Similarity-матрицы, skill-профили профессий, career-transition граф — строятся батчами оффлайн, не в рантайме запроса пользователя.
4. **Замещаемость.** Каждый адаптер (Lightcast, ESCO, work.ua) можно отключить; ядро деградирует, но не падает.
5. **LLM изолирован.** CV-parsing, объяснения, коучинг — отдельный сервис (AI Gateway, уже есть — `app/ai_gateway.py`). Career matching — детерминированный код.

**Если берём Lightcast API:**
- Скоупы: `lightcast_open` / `classification_api` (навыки), при контракте — `career-pathways`, `role-pricing` и т.д.
- Rate limits (`CONFIRMED`): Classification 5 req/s; Core LMI 300/5min; Occupation Benchmark 5 req/s; Market Salary unlimited (default). → батч-обработка, не пользовательский рантайм.
- OAuth2 bearer, TTL токена 1 час.

---

# 13. Licensing — критический блок

**Open Terms of Use (для «Open» линейки: Skills, Titles, часть Occupations) — `CONFIRMED` ([v1.2](https://legal.lightcast.io/lightcast-legal/open-terms-of-use?v=1.2)):**
- Грант: «limited, personal, royalty-free, fully paid-up, perpetual, non-transferable, non-sublicensable, worldwide».
- **По умолчанию — только non-commercial** («copy and redistribute … transform and build upon … for non-commercial purposes only»).
- Коммерческое использование — «may be permitted provided the user contacts Lightcast and enters into a written contract».
- Можно сделать данные частью проприетарного платного приложения — но нельзя накладывать на сам Dataset ограничения строже этой лицензии (`CONFIRMED` — формулировка из FAQ/terms).
- **Атрибуция обязательна и на видном месте** + ссылка на лицензию + уведомление об изменениях.
- Нельзя передавать API-ключ / инстанс Data Share другим (`CONFIRMED`).
- Termination: «Lightcast reserves the right to cancel or suspend access … at any time, for any reason». Что происходит с уже сохранёнными данными — **не сказано** (`UNKNOWN`).

**General Terms of Service / коммерческий контракт — `INFERENCE` из [general TOS](https://legal.lightcast.io/lightcast-legal/general-terms-of-service) и [публикации условий Lightcast партнёром Watermark Insights](https://www.watermarkinsights.com/legal/lightcast-terms/):**
- Есть пункт об **удалении Content в течение ~30 рабочих дней после окончания договора** (`INFERENCE` — Section 4.5 в общей редакции; конкретный продуктовый addendum может отличаться).
- Ограничения на редистрибуцию третьим лицам, sublicense, repackage, rebrand.
- Атрибуция к Lightcast в публикуемых материалах.
- Downstream-условия (как у Watermark) бывают жёстче: «no derivative works», «cannot distribute as stand-alone product».

**Ключевые вопросы — все `MUST ASK LIGHTCAST`:**

| Вопрос | Статус |
|---|---|
| Можно ли кэшировать ответы API? | `MUST ASK` (вероятно да, операционно) |
| Можно ли хранить их **постоянно** (не удаляя)? | `MUST ASK` — конфликтует с «delete within 30 days of termination» |
| Можно ли показывать данные Lightcast **B2C-пользователям** внутри платного продукта? | `MUST ASK` — нужен коммерческий контракт + вероятно атрибуция на экране |
| Можно ли строить **derived scores** (наши transition/gap/fit баллы на основе Lightcast)? | `MUST ASK` — «transform and build upon» разрешено, но коммерческое — контракт; downstream-редакции запрещают «derivative works» |
| Можно ли **обучать собственные модели/алгоритмы** на данных Lightcast? | `MUST ASK` / `UNKNOWN` — общий TOS упоминает запрет reverse engineering и derivative works; про ML-обучение прямо не сказано |
| Что с данными после прекращения договора? | `MUST ASK` — вероятно обязаны удалить в 30 дней; тогда наши derived-данные под вопросом |
| Требования к атрибуции в UI | `MUST ASK` — формат, размещение |
| Разрешена ли агрегация с work.ua/robota.ua/ESCO в едином продукте | `MUST ASK` |

**Вывод §13 (жёсткий):** **лицензионная модель Lightcast структурно недружелюбна к тому, чтобы делать его ядром коммерческого B2C-продукта с длительным хранением derived-данных.** «Perpetual» в Open-лицензии относится к non-commercial. Коммерческий контракт, вероятно, требует удаления данных при расторжении. → ещё один аргумент строить ядро (Career KB, Skill IDs, transition-модель) на открытых источниках (ESCO/O*NET), а Lightcast использовать точечно и заместимо.

---

# 14. GDPR & Security

**Что подтверждено (`CONFIRMED` — [Lightcast Privacy Policy](https://legal.lightcast.io/lightcast-legal/privacy-policy), [general TOS](https://legal.lightcast.io/lightcast-legal/general-terms-of-service)):**
- Услуги «compliant-by-design» под GDPR и CCPA.
- Если стороны заключают DPA — он имеет приоритет над остальными условиями.
- Список субпроцессоров: **trust.lightcast.io** (`CONFIRMED` — ссылка упоминается).
- Трансграничная передача — через **Standard Contractual Clauses (SCCs)**.
- Контролёр — Obsidian BG Holdings LP и группа (Lightcast LLC (US), Lightcast Solutions Canada Inc., **Lightcast SRL Europe** (Италия/ЕС)).
- Права субъектов ЕС/ЕЭЗ/UK: доступ, исправление, удаление, ограничение, возражение, отзыв согласия, портируемость. Есть форма DSAR.

**Что неизвестно — всё критично, если мы отправляем CV украинского/ЕС пользователя в Lightcast API:**

| Вопрос | Статус |
|---|---|
| Где физически обрабатываются данные, отправленные в Classification API (US / EU)? | `UNKNOWN` / `MUST ASK LIGHTCAST` |
| Есть ли опция EU-only processing / data residency? | `UNKNOWN` / `MUST ASK` (для enterprise упоминаются «data residency options» — `INFERENCE`) |
| Retention присланного текста CV | `UNKNOWN` / `MUST ASK` |
| Обучают ли модели на присланных клиентом данных? | **`UNKNOWN` — Privacy Policy молчит. `MUST ASK` (критично).** |
| Удаление по запросу | `INFERENCE` — да (есть DSAR), но SLA `UNKNOWN` |
| Готовы ли подписать DPA с нами | `INFERENCE` — да для enterprise; `MUST ASK` |
| Список субпроцессоров (кто именно) | `MUST ASK` — проверить trust.lightcast.io перед интеграцией |

**Вывод §14:** до подписания DPA и получения письменного подтверждения (1) места обработки, (2) отсутствия обучения на наших данных, (3) retention — **не отправлять реальные CV пользователей в Lightcast.** Безопасная альтернатива для V1: парсинг CV локально (наш LLM через AI Gateway с собственным DPA у LLM-провайдера) + отправлять в Lightcast только **обезличенные нормализованные токены** (список навыков/должностей на английском), не сырой текст с ФИО/контактами. Это резко снижает GDPR-поверхность.

---

# 15. Pricing

**Публичных прайс-листов на API/данные у Lightcast нет** (`CONFIRMED` — все страницы pricing ведут на «talk to a Data Pro»).

**Что найдено (проверяемые источники):**

| Год | Продукт | Клиент / сегмент | Цена | Источник |
|---|---|---|---|---|
| 2022 (ноя) | «Developer» (economic/workforce dev community tool) | EDCC (economic development, US) | **1 год:** $5 000 (регион <50k нас.) / $8 000 (50–200k) / $12 000 (200k+); 3 места. **2 года:** $4 000 / $7 000 / $10 000 в год. Add-ons: National Data $3 000, Profile Analytics $2 500, Business Listings $2 500 | [EDCC Partnership deck, Nathan Foss, Account Executive](https://edcconline.org/wp-content/uploads/2022/11/EDCC-Pricing-Updated-Lightcast.pdf) `CONFIRMED` |
| 2026 | Lightcast data (обучение) | World Bank / проект COLABORA (Латинская Америка) | Модель доступа не раскрыта в публичной версии слайдов | [World Bank docs — «Introduction to Lightcast Data and Skills», Feb 2026](https://thedocs.worldbank.org/en/doc/9074de6ad9bee77a6c5bee1d35ab417e-0370022026/original/COLABORA-Feb-2026-Introduction-to-Lightcast-Data-and-Skills-Matt-Walsh-ESP.pdf) `CONFIRMED` (существование контракта), детали `UNKNOWN` |
| — | Академический доступ (переупаковка) | Исследователи / вузы | Через **Dewey Data** (data marketplace) — 4 датасета Lightcast + 2 из Rhetorik; цены не раскрыты | [deweydata.io/data-partners/lightcast](https://www.deweydata.io/data-partners/lightcast) `CONFIRMED` (канал), цены `UNKNOWN` |

**Что известно про структуру (`CONFIRMED` из общих материалов):**
- Community-тариб (US/CA economic dev) — 4–5-значные суммы в год.
- Enterprise API — custom-negotiated: dedicated capacity, SLA, security review, data residency options, named TAM.
- Open Skills API — «на контрактной основе» (бесплатного публичного tier для продакшена больше нет — `CONFIRMED` [FAQ](https://lightcast.io/open-skills/faqs)).
- Nonprofit — «full access, free of charge» по регистрации (`CONFIRMED` — [Open Skills / нескол. страниц]); относится, `INFERENCE`, в первую очередь к Skills-таксономии, не ко всему каталогу.

**Что не найдено (`UNKNOWN`):** цена Career Pathways API, Job Postings API, Compensation API; минимальный контракт; наличие sandbox/trial с кредитами; startup-программа; government/EU pricing для не-US.

**`INFERENCE` (диапазон, не факт):** полноценный коммерческий контракт с несколькими API (postings + pathways + compensation + skills) для B2C-продукта — ориентировочно **десятки тысяч USD в год и выше**, с годовым минимумом. Для стартапа на этапе валидации — существенно. `MUST ASK LIGHTCAST` — точные цифры, наличие pilot/startup-условий.

---

# 16. Nonprofit / Ukraine Partnership

**Что подтверждено:**
- Нонпрофиты получают бесплатный доступ к **Lightcast Skills** по регистрации (`CONFIRMED` — [Open Skills](https://lightcast.io/open-skills)). Масштаб — Skills, не весь каталог (`INFERENCE`).
- Lightcast Skills используется Stanford AI Index, WEF Future of Jobs (`CONFIRMED` — [our-taxonomies](https://lightcast.io/products/data/our-taxonomies)) — компания ценит присутствие в public-good проектах.
- **World Bank** уже работает с Lightcast (проект COLABORA, обучение по данным и навыкам, Feb 2026) (`CONFIRMED` — [World Bank docs](https://thedocs.worldbank.org/en/doc/9074de6ad9bee77a6c5bee1d35ab417e-0370022026/original/COLABORA-Feb-2026-Introduction-to-Lightcast-Data-and-Skills-Matt-Walsh-ESP.pdf)).
- Академический доступ — через институциональные лицензии или Dewey Data.

**Что не найдено (`UNKNOWN` / `MUST ASK`):**
- Формальная «Lightcast Foundation» / «Data for Good» программа с процессом подачи заявки — **не обнаружена публично.**
- Специальные инициативы по Украине, беженцам, ветеранам, workforce recovery со стороны Lightcast — **не обнаружены.**
- Условия pilot / discounted / grant для соц-проектов — `UNKNOWN`.

**Кому направлять partnership request (`INFERENCE`):**
1. **Lightcast «Data for Good» / Social Impact / Public Sector** команда — через форму «Speak with a Data Pro» с явной пометкой «Ukraine workforce recovery / nonprofit».
2. **Economic & Workforce Development («Lightcast Community»)** — сегмент, который занимается reskilling/workforce agencies; в EDCC-деке контакт: **Nathan Foss, Account Executive** (публичный из [дека](https://edcconline.org/wp-content/uploads/2022/11/EDCC-Pricing-Updated-Lightcast.pdf)) — как пример роли, не обязательно текущий владелец региона.
3. **Через World Bank / ILO / EU4Skills / USAID-партнёров** — если MNP входит в их программы по Украине, попросить их представить нас команде Lightcast, с которой они уже работают (COLABORA).
4. **Research/Academic team** — если оформить пилот как исследование результатов reskilling ВПО/ветеранов.

**Наш use case для питча:** украинская персональная Career Navigation Platform для reskilling, workforce recovery, ВПО, ветеранов, безработных и украинцев, рассматривающих возвращение. Социальный + коммерческий импакт. Пилот — §24.

---

# 17. Build vs Buy Matrix

Легенда: **BUILD** — наш IP, строим сами. **BUY** — лицензируем у Lightcast. **HYBRID** — методология/каркас извне, данные/логика/украинский слой — наши. **OPEN** — берём из ESCO/O*NET/ДСЗ (открытое), не из Lightcast.

| MNP Component | Build ourselves | Lightcast | Hybrid / Open | Recommendation |
|---|---|---|---|---|
| Career taxonomy (структура) | скелет | LOT как один вход | ESCO + ISCO + КП України | **OPEN + BUILD** (MNP Career ID) |
| Skills taxonomy | mapping-слой | tech/digital навыки опц. | **ESCO ядро** + O*NET | **OPEN + HYBRID** (MNP Skill ID; Lightcast опц.) |
| CV parsing (текст → поля) | промпты/валидация | — | LLM (AI Gateway) | **BUILD** (LLM-ассист) |
| Skills extraction (текст → навыки) | — | Classification API кандидат | ESCO skill-matcher + LLM | **HYBRID** (тест: Lightcast Classification vs свой на англ. части) |
| Title normalization | UA-слой | Titles taxonomy (EN) | ESCO + work.ua титулы | **HYBRID** (EN — Lightcast/ESCO; UA — свой) |
| Occupation normalization | UA-слой | LOT/O*NET кросс-уок | ESCO + ISCO | **OPEN + BUILD** |
| Career Card (структурированный профиль) | вся логика | — | — | **BUILD (ядро IP)** |
| Career Graph / KB | кураторская KB (см. doc 14) | similarity как референс | O*NET признаки | **BUILD (кураторская, не full graph)** |
| Career transitions (A→B) | движок | Pathways как эталон (US) | методология + ESCO/O*NET векторы | **BUILD (ядро IP)**, калибровка по Lightcast |
| Skill gap (person → target) | движок + персонализация | occ→occ методология + salary-signal | — | **HYBRID → BUILD** |
| Salary (Украина) | агрегация | глобальный ориентир | work.ua / robota.ua | **BUILD на UA-бордах** |
| Labour demand (Украина) | агрегация | ❌ | work.ua / robota.ua / ДСЗ | **BUILD на UA-бордах** |
| Job postings (Украина) | коннекторы | ❌ (Set 3/4) | work.ua / robota.ua / OLX / ДСЗ | **BUILD (DATA-002)** |
| Employers (Украина) | — | ❌ | UA-борды + YouControl/Clarity | **BUILD / OPEN** |
| Education / training catalog | кураторский | ❌ | ДСЗ + Prometheus/EdEra + вузы | **BUILD** |
| Feasibility scoring (под Украину + ограничения) | вся логика | ❌ | — | **BUILD (ядро IP)** |
| Opportunity matching | движок | ❌ | UA-борды | **BUILD (ядро IP)** |
| Career recommendations (TOP-N) | движок | ❌ | — | **BUILD (ядро IP)** |
| User explanations / coaching | промпты | ❌ | LLM (AI Gateway) | **BUILD (LLM)** |
| Emerging/declining skills (глобально) | — | Projected Skill Growth | WEF Future of Jobs (открытый отчёт) | **BUY опц. / OPEN** |
| International benchmark (для персон «выезд/возврат») | — | Job Postings Global / Compensation (ЕС) | Eurostat, EURES | **BUY опц. / OPEN** |

**Итого:** из ~21 компонента — **BUILD/OPEN: 15**, **HYBRID: 4**, **BUY (опционально, заместимо): 2**. Ни один компонент критического пути не является чистым BUY.

---

# 18. Dependency / Risk Analysis

| Риск | Оценка | Обоснование | Митигация |
|---|---|---|---|
| **Vendor lock-in** | 🔴 Высокий, если строить ядро на Lightcast IDs | Skill/Occupation IDs непереносимы; таксономия меняется ежемесячно/ежегодно | MNP Skill/Career ID + mapping-слой; ESCO как ядро |
| **Pricing risk** | 🟠 Средний-высокий | Нет публичных цен; custom-negotiated; годовой минимум; при росте пользователей цена может расти | Не делать критический путь зависимым; бюджетный кэп; готовый fallback на ESCO/O*NET |
| **API limits** | 🟢 Низкий | 5 req/s хватает для батч-обработки; не пользовательский рантайм | Оффлайн-построение матриц; кэш |
| **Termination risk** | 🔴 Высокий | «cancel/suspend at any time, for any reason»; вероятное удаление данных в 30 дней после расторжения | Хранить только заместимые данные; ядро не зависит; снапшоты открытых источников |
| **Data export** | 🟠 Средний | Data Share даёт bulk, но при расторжении — удалить | Держать собственную нормализованную копию только того, что лицензия позволяет |
| **Taxonomy changes** | 🟠 Средний | LOT годовой цикл, Skills ежемесячно; ломает downstream | Версионирование в нашей KB (уже принцип — doc 13 founder review); mapping-таблицы с версиями |
| **Coverage degradation (Украина)** | 🟠 Средний | Set 3/4 «sporadic or unreliable» по прямому признанию Lightcast | Не использовать Lightcast для украинского спроса вообще |
| **Невозможность хранить derived data** | 🔴 Высокий | Лицензия может запретить постоянное хранение наших баллов на базе Lightcast | `MUST ASK`; при негативном ответе — не строить scoring на Lightcast |
| **Зависимость core IP MNP от Lightcast** | 🟢 Низкий при рекомендованной архитектуре | Career Card, transition engine, feasibility, matching — наши | Держать так |
| **GDPR (CV в Lightcast)** | 🔴 Высокий до DPA | Место обработки, обучение на данных, retention — `UNKNOWN` | Не слать сырой CV; только обезличенные токены; DPA до интеграции |
| **Смена владельца / стратегии** (KKR — PE, горизонт выхода) | 🟠 Средний | PE-владелец → возможен IPO/перепродажа → изменение условий/цен | Заместимая архитектура; не подписывать многолетний эксклюзив |

**Архитектурный принцип устойчивости (`INFERENCE`):**
> Lightcast имеет право быть **ускорителем** (быстрее собрать таксономию и откалибровать методологию переходов), но **не единственной точкой отказа**. Тест: «если завтра Lightcast отключит нам доступ и потребует удалить данные — продукт продолжает работать на ESCO/O*NET/work.ua/robota.ua/ДСЗ с деградацией качества таксономии, но без остановки». Архитектура из §11–§12 этот тест проходит.

---

# 19. Five Ukrainian Personas

Для каждой: что даёт Lightcast · чего не знает · что добавляет MNP · итог пользователю.

### Persona A — Бухгалтер, хоче більше заробляти
- **Lightcast:** skill-профиль профессии «Accountant/Bookkeeper» (LOT/O*NET); next-step для US (Financial Analyst, Financial Controller, Auditor) с relevance score; transitional skills (financial modeling, SQL, data visualization, IFRS) с importance; salary-boosting skills (US).
- **Не знает:** украинский спрос на бухгалтеров и смежные роли; украинские зарплаты и реальную «прибавку» перехода; какие курсы доступны в Украине; что этот конкретный человек уже умеет.
- **MNP добавляет:** Career Card из её CV (1С, налоговый учёт, ФОП, зарплатные проекты); transferable skills; feasibility перехода в «Фінансовий аналітик»/«Внутрішній аудитор»/«Data Analyst у фінансах» с учётом её ограничений (город, дети, англ. уровень); skill gap именно для неё; вакансии на work.ua/robota.ua сейчас; медианные зарплаты по обеим ролям в Украине; план на 90 днів.
- **Итог:** «Найближчий вигідний перехід — Фінансовий аналітик. У Києві зараз N вакансій, медіана +40% до вашого рівня. Вам не вистачає 4 навичок: фінмоделювання в Excel, Power BI, SQL, МСФЗ. Ось курси і 2 стажування.»

### Persona B — Продавець-касир, хоче в офісну/digital професію
- **Lightcast:** feeder/next-step для «Retail Salesperson» (US) → часто Customer Support, Sales Coordinator, Account Manager; transferable — communication, CRM, conflict resolution.
- **Не знает:** есть ли в Украине спрос на entry-level support/HR-admin/junior-роли; какие украинские компании берут без опыта; украинские зарплаты; что доступно бесплатно выучить (ДСЗ-ваучер).
- **MNP добавляет:** извлечение transferable skills из неструктурного опыта (работа с людьми, касса = внимательность к деталям + работа с ПЗ); reality-check по entry-барьеру в Украине; матчинг на «Оператор кол-центру», «Менеджер з підтримки клієнтів», «Асистент відділу»; путь через ДСЗ-переобучение.
- **Итог:** «Реалістичний перший крок — підтримка клієнтів (не «продажник»). N вакансій, поріг входу низький, зарплата X. За 6–8 тижнів курсу (є ваучер ДСЗ) ви закриваєте розрив.»

### Persona C — Керівник відділу продажів, шукає adjacent career
- **Lightcast:** lateral-переходы для «Sales Manager» (US) → Business Development Director, Revenue Operations, Partnerships, Customer Success Lead; DDN-навыки роли; salary-сравнение (US).
- **Не знает:** глубину украинского рынка для RevOps/Partnerships (ниша, мало вакансий); какие из adjacent-ролей реально нанимают в Украине vs только в международных компаниях/удалёнке.
- **MNP добавляет:** различение «украинский рынок» vs «международная удалёнка из Украины» как отдельные opportunity-каналы; feasibility с учётом английского и опыта; какие навыки/кейсы «доказать» (не «выучить») для перехода; конкретные вакансии и компании.
- **Итог:** «У межах України adjacent-варіант з попитом — Head of Customer Success. RevOps в Україні майже немає, але 30+ віддалених вакансій у міжнародних компаніях. Для них потрібно: показати досвід із CRM-аналітикою і 1 кейс зростання retention.»

### Persona D — Людина з військовим досвідом, повертається на цивільний ринок
- **Lightcast:** в США есть military-crosswalk (O*NET/MOS→SOC) — Lightcast частично это поддерживает для US; skill-профили гражданских ролей.
- **Не знает:** украинского аналога military→civilian crosswalk; украинского спроса; программ для ветеранов в Украине; как украинские работодатели читают военный опыт.
- **MNP добавляет:** **это ядро ценности MNP** — перевод военного опыта (командование, логистика, связь, БПЛА, медицина, безопасность, обучение личного состава) в гражданские навыки и роли (операционный менеджмент, логистика, project management, безопасность, GIS/дрони, парамедик, інструктор); feasibility; ветеранские программы и квоты; вакансии.
- **Итог:** «Ваш досвід управління підрозділом = операційний/проєктний менеджмент. 3 напрями: керівник логістики, координатор проєктів, оператор БПЛА в цивільному секторі. Ось що додати до резюме, ветеранські програми і N вакансій.»

### Persona E — Українець повертається з Німеччини, хоче заздалегідь зрозуміти можливості в Україні
- **Lightcast:** сильная сторона — **Job Postings Global / Compensation по Германии** (Set 2): что человек делал/зарабатывал в DE, какие навыки там ценятся; глобальный skill-профиль его профессии.
- **Не знает:** что из немецкого опыта конвертируется в украинский рынок; украинские зарплаты (для решения «стоит ли возвращаться финансово»); украинский спрос; релокационные/реинтеграционные программы.
- **MNP добавляет:** сравнение «DE ↔ UA» по его профессии (зарплата, спрос, ниши); какие навыки/сертификаты, полученные в DE, дают премию в Украине; feasibility возвращения по ролям; реинтеграционные программы; удалёнка на DE-рынок из Украины как отдельный сценарий.
- **Итог:** «У Німеччині ви — Mechatronics Technician. В Україні пряма роль оплачується на X (нижче на Y%), але ваш досвід EU-стандартів дає премію на промислових підприємствах Заходу України та у міжнародних компаніях. Варіант: залишити частину доходу через віддалену роботу на DE. Ось вакансії і програми повернення.»

**Сводка по персонам:** Lightcast полезен для Persona E (данные по стране пребывания) и частично для методологии переходов у A/C. Для B и D — **вся ценность у MNP**, Lightcast почти не участвует. Ни для одной персоны Lightcast не даёт украинский спрос/зарплату/вакансии.

---

# 20. End-to-End Transition Prototype

**Кейс: Бухгалтер (Accountant) → Фінансовий аналітик (Financial Analyst), Україна.**

| Поле | Значение (иллюстративное) | Источник |
|---|---|---|
| Raw CV → job titles | «Головний бухгалтер», «Бухгалтер», «Помічник бухгалтера» | `MNP CALCULATION` (LLM parsing) |
| Normalized title (EN) | Chief Accountant / Accountant | `LIGHTCAST` Titles / `ESCO` (EN) |
| Normalized occupation | ISCO 2411 «Accountants» / ESCO «accountant» / КП 2411.2 | `ESCO` + `MNP` (mapping на КП України) |
| Current skills (из CV) | бухоблік, податковий облік, 1С:Бухгалтерія, BAS, зарплата і кадри, звітність, ПДВ, МСФЗ (базово), Excel | `MNP CALCULATION` (LLM + ESCO skill-match) |
| Transferable skills | фінансова звітність, аналіз даних, увага до деталей, знання регуляторики, робота з ERP | `MNP CALCULATION` (методология DDN/similarity) |
| Target occupation skill-профиль | financial modeling, forecasting, variance analysis, Excel (advanced), SQL, Power BI/Tableau, valuation, IFRS, business partnering | `ESCO` + `O*NET` (13-2051 Financial Analysts) + `LIGHTCAST` (если контракт) |
| Missing skills (gap, направленно) | 1) фінансове моделювання, 2) Power BI, 3) SQL, 4) прогнозування/бюджетування, 5) поглиблені МСФЗ | `MNP CALCULATION` (gap = target − current, формула Lightcast) |
| Transition score / feasibility | ~0.72 (высокая — общий фундамент «финансы/учёт», разрыв закрывается обучением, без нового диплома) | `MNP CALCULATION` (similarity + education/experience gap) |
| Education gap | Нет (обе роли — вища освіта економічного профілю; диплом бухгалтера подходит) | `O*NET` job zone + `MNP` (UA-специфика) |
| Experience gap | 0–1 год релевантного (аналитические задачи); переход на junior/middle analyst | `MNP CALCULATION` |
| Ukraine demand (вакансії зараз) | work.ua: N вакансій «Фінансовий аналітик» + M «Аналітик» | `WORK.UA` / `ROBOTA.UA` |
| Ukraine demand (динаміка 12 міс.) | +Y% | `WORK.UA` / `ROBOTA.UA` (при наличии истории) / `UNKNOWN` если истории нет |
| Ukraine salary — Accountant | медіана A грн | `WORK.UA` / `ROBOTA.UA` |
| Ukraine salary — Financial Analyst | медіана B грн (B > A на ~30–45%) | `WORK.UA` / `ROBOTA.UA` |
| Income upside | +(B−A) грн/міс | `MNP CALCULATION` |
| Transition time | 4–7 місяців (навчання паралельно з роботою) | `MNP CALCULATION` (learnability модель) |
| Recommended learning | Курс фінмоделювання (Excel), Power BI (безкоштовно MS Learn), SQL basics, курс МСФЗ; можливий ваучер ДСЗ | `MNP` curated catalog + `ДСЗ` |
| Current vacancies (конкретні) | 5–10 карток з work.ua/robota.ua з посиланнями | `WORK.UA` / `ROBOTA.UA` |
| Global context (для мотивації) | Financial Analyst у ЄС: €X; в топ-навичках — SQL, Python | `LIGHTCAST` Job Postings Global / `UNKNOWN` без контракту |

**Оценка «сколько собирается»:** из ~20 полей цепочки —
- полностью нашими силами + открытые источники (`MNP` / `ESCO` / `O*NET` / `WORK.UA` / `ROBOTA.UA` / `ДСЗ`): **~16 полей (80%)**;
- заметно улучшается с Lightcast (skill-профиль target, global context, salary-boosting skills): **~3 поля**;
- `UNKNOWN` без дополнительной работы (динамика спроса, если у UA-бордов нет истории API): **~1 поле**.

**Вывод §20: цепочка собирается на ~80% без Lightcast.** Порог Founder (70–80%) пройден **за счёт open-источников и наших расчётов**, а не за счёт Lightcast. Lightcast улучшает качество skill-профилей и добавляет международный контекст, но не является тем, что делает цепочку возможной.

---

# 21. What We Do Not Need to Build

### DO NOT BUILD (взять готовое — открытое или у Lightcast)
- **Базовую таксономию навыков с нуля** → ESCO (ядро) + Lightcast Skills (tech/digital, опц.). 34k навыков вручную не составляем.
- **Базовую таксономию профессий с нуля** → ESCO + ISCO + КП України + O*NET-признаки.
- **Модель «признаки профессии» (abilities, work activities, work context, job zones)** → O*NET, полностью открыт.
- **Методологию occupation-similarity и career-pathways** → документирована Lightcast, воспроизводим, не изобретаем.
- **Собственный публичный отчёт о будущем навыков** → WEF Future of Jobs, Lightcast-отчёты.
- **NER для навыков на английском** → Classification API кандидат / готовые ESCO-матчеры.

### BUILD OURSELVES (наш IP и конкурентное преимущество)
- **Career Card** (CV/опыт/образование → структурированный профиль с transferable skills).
- **Person → Occupation matching** (не occupation→occupation, а «этот человек → эти направления»).
- **Feasibility scoring под Украину** с учётом ограничений пользователя (город, семья, английский, финансовая подушка, срочность, ВПО/ветеран-статус).
- **Career Transition Engine** (5 переходов + skill gap персонализированный + income upside в гривне + время).
- **Украинский слой:** UA-названия профессий/навыков, UA→EN нормализация, украинский спрос/зарплаты (агрегация work.ua/robota.ua/ДСЗ), каталог украинского обучения.
- **Opportunity matching** (профиль → реальные вакансии/стажировки/программы).
- **Объяснения и коучинг** (LLM поверх детерминированного результата).
- **Golden-test набор для украинских кейсов** (см. doc 22).

### PARTNER / LICENSE (покупать или получать через партнёров)
- **Lightcast Skills (tech/digital навыки)** — по nonprofit-регистрации или контракту.
- **Lightcast Classification API** — если тест покажет превосходство над своим решением на англ. части CV.
- **Международные бенчмарки (Job Postings Global / Compensation по ЕС)** — для персон «выезд/возврат», опционально.
- **Доступ work.ua / robota.ua** — отдельная задача **DATA-002** (официальный API / партнёрство).
- **ДСЗ open data** — интеграция, не покупка.

---

# 22. What Remains MNP Core IP

Формально фиксируем — это **нельзя** отдавать во внешнюю зависимость:

1. **Career Card model** — способ превращать разнородный украинский опыт (включая военный, неформальный, самозанятость) в структурированный переносимый профиль.
2. **Feasibility / Transition scoring** — веса и логика, учитывающие украинский контекст и личные ограничения. Это то, что отличает MNP от «профориентационного теста».
3. **Ukrainian Career Knowledge Base** — кураторская, версионируемая, с mapping-слоем на все внешние стандарты. Мы контролируем ID и структуру.
4. **UA lexical layer** — словари названий профессий/навыков, синонимы, UA→EN нормализация.
5. **Persona-specific logic** — ветераны, ВПО, возвращенцы: правила перевода опыта и подбора программ.
6. **Opportunity graph (Украина)** — связь профиль → вакансия/стажировка/программа/ваучер.
7. **Explanation layer** — как результат объясняется пользователю (тон, доказательность, следующий шаг).
8. **Golden dataset** — эталонные украинские кейсы для регрессионного контроля качества рекомендаций.

Всё это — детерминированное ядро (соответствует doc 14: ядро data-driven, LLM не на каждом шаге).

---

# 23. Questions for Lightcast

Только то, чего нет в публичной документации.

**Ukraine coverage**
1. В каком Set (1/2/3/4) находится Украина по состоянию на 2026? 
2. Сколько job postings/месяц Lightcast собирает по Украине? Из каких источников (перечислите — есть ли work.ua, robota.ua, OLX)?
3. Какая глубина истории постингов по Украине (с какого года)?
4. Какой % постингов по Украине содержит advertised salary?
5. Сколько worker profiles по Украине? Достаточно ли для statistically-sound career-transition анализа?
6. Покрывают ли Compensation API / Role Pricing Украину? Какая методология и заявленная погрешность для UA?
7. Есть ли workforce estimates (WEMo) по Украине и на каком уровне (страна/область)?
8. Планы по улучшению покрытия Украины на 12–24 месяца?

**Украинский язык**
9. Полный список языков, поддерживаемых JPA и Classification API. Входит ли украинский? Русский?
10. Распознаёт ли Classification API украиноязычные названия должностей и навыков?
11. Есть ли украиноязычные aliases в Skills/Titles/Occupation таксономиях?
12. Как обрабатывается смешанный UA/EN текст резюме?

**Career Pathways**
13. Подтвердите: Career Pathways API доступен только для US/CA/UK?
14. Что технически нужно, чтобы Lightcast построил Career Pathways для Украины? Сроки/условия?
15. Предоставьте реальные примеры request/response JSON для Career Pathways API и Skill Gap.
16. Есть ли sandbox / trial-доступ к Career Pathways и Classification для оценки?
17. Career Pathways строится на профилях, постингах или обоих? Как именно взвешиваются factual transitions vs skill-similarity?

**Pricing**
18. Ориентировочная стоимость годового контракта для B2C-стартапа: Skills API + Classification API?
19. Стоимость добавления Career Pathways + Compensation API?
20. Есть ли минимальный контракт / годовой минимум? Startup-программа? Pilot-цена?
21. Условия nonprofit-доступа: что именно бесплатно (только Skills-таксономия или API тоже)?

**Licensing**
22. Можно ли постоянно хранить (кэшировать без удаления) ответы API в нашей БД в течение действия договора?
23. Можно ли показывать данные Lightcast конечным пользователям (B2C) внутри платного продукта? Требования к атрибуции в UI?
24. Можно ли строить и постоянно хранить наши собственные производные баллы (transition/fit/gap scores), рассчитанные с использованием данных Lightcast?
25. Разрешено ли обучать собственные ML-модели/алгоритмы на данных Lightcast?
26. Что происходит с кэшированными данными и производными баллами после прекращения договора? Обязаны ли мы их удалить (30 дней)?
27. Разрешена ли агрегация данных Lightcast с данными work.ua/robota.ua/ESCO в едином продукте?

**GDPR / Security**
28. Где физически обрабатываются данные, отправленные в Classification API (регион)? Есть ли EU-only / data residency опция?
29. Как долго хранится присланный текст резюме? Используются ли присланные клиентом данные для обучения ваших моделей?
30. Подпишете ли вы DPA (Data Processing Agreement) с нами? Актуальный список субпроцессоров?

**Roadmap / Partnership**
31. Есть ли у Lightcast программа «Data for Good» / социального impact с процессом подачи заявки?
32. Работает ли Lightcast с проектами по восстановлению рынка труда Украины (World Bank, ILO, EU, USAID)? Можно ли присоединиться к существующей инициативе?

---

# 24. Partnership Proposal (one-pager)

> **Lightcast × «Мій Напрям» / Ukraine — Pilot Proposal**
>
> **Концепция.** «Мій Напрям» (МОЖУ) — персональная Career Navigation платформа для взрослых украинцев: поиск работы после потери, смена профессии, рост дохода, реинтеграция ВПО и ветеранов, планирование возвращения из-за границы. Ядро — детерминированный движок карьерных переходов: CV → Career Card → transferable skills → возможные переходы → FIT + FEASIBILITY + спрос + рост дохода → TOP-направления → skill gap → что выучить/доказать → реальные вакансии и программы.
>
> **Что мы приносим:**
> - Доступ к украинской аудитории в масштабе (ВПО, ветераны, безработные, возвращенцы) через государственных и НГО-партнёров.
> - Собственный украинский слой: спрос/зарплаты (work.ua/robota.ua/ДСЗ), UA-таксономия, кураторская Career KB, feasibility-модель.
> - Кейс использования Lightcast Skills / методологии в контексте workforce recovery — публикуемый (с согласия Lightcast) impact-результат для их social-impact нарратива (аналогично Stanford AI Index / WEF).
> - Обратную связь по качеству таксономии на украинских/русскоязычных данных.
>
> **О чём просим Lightcast:**
> - Pilot-доступ (6–12 мес.) к: Skills API / Classification API (skill extraction, title/occupation normalization) + Career Pathways + Skill Gap (US/CA/UK — как методологический эталон для калибровки нашего движка).
> - Nonprofit / discounted / grant условия на пилотный период.
> - Техническую консультацию по адаптации методологии переходов к рынку без глубоких job-posting данных.
> - Прояснение лицензии для B2C-продукта социального назначения.
> - (Стретч) обсуждение построения Career Pathways для Украины при достижении Lightcast достаточного покрытия.
>
> **Пилот (предлагаемый scope):**
> 1. 500–1000 реальных украинских пользователей проходят полную цепочку.
> 2. Замер: качество skill-extraction (Lightcast Classification vs наш baseline) на украинских CV (переведённых); совпадение наших transition-рекомендаций с Lightcast Career Pathways на эквивалентных US-профессиях; доля пользователей, дошедших до действия (обучение/отклик/собеседование).
> 3. Итог: совместный short report о применимости labour-market intelligence в восстановлении рынка труда Украины.
>
> **Ценность:**
> - *Социальная:* ускоренный reskilling и трудоустройство уязвимых групп; данные для государственной политики занятости.
> - *Коммерческая для Lightcast:* вход на украинский рынок через валидированного локального партнёра; референс-кейс social impact; расширение покрытия Украины на реальных пользовательских данных.
>
> **Контакт для маршрутизации запроса:** Lightcast Social Impact / Public Sector / Economic & Workforce Development team (через «Speak with a Data Pro» с пометкой Ukraine nonprofit); либо интро через World Bank / ILO-контакты, уже работающие с Lightcast (проект COLABORA).

---

# 25. Founder Recommendation

### A. Использовать ли Lightcast в MNP?
**PILOT FIRST.** Не подписывать полный коммерческий контракт до: (1) созвона и ответов на §23; (2) прохождения пилота §24; (3) прохождения золотого теста §20 на реальных украинских кейсах. По итогам исследования — Lightcast **полезен, но не необходим** для V1. Для V1 можно стартовать вообще без Lightcast (на ESCO/O*NET/work.ua/robota.ua/ДСЗ) и добавить Lightcast позже точечно.

### B. Что именно использовать (если пилот успешен)?
- **Lightcast Skills таксономия** — как дополнение к ESCO для tech/digital навыков (по nonprofit-регистрации, бесплатно, если подтвердится).
- **Lightcast Classification API** — для skill extraction / title normalization на англоязычной (переведённой) части CV — **только если** тест покажет превосходство над нашим ESCO+LLM baseline.
- **Career Pathways + Skill Gap (US/CA/UK)** — краткосрочно, как **эталон для калибровки** нашего Transition Engine, не как продакшн-зависимость.
- **Job Postings Global / Compensation (ЕС)** — опционально, для персон «выезд/возврат».
- **НЕ брать:** Assessments API (RIASEC — не наш подход), Core LMI (US only), IPEDS, всё US-education.

### C. Что НЕ отдавать Lightcast (остаётся нашим IP)?
Всё из §22. Прежде всего: Career Card model, Feasibility/Transition scoring, Ukrainian Career KB с собственными ID, UA lexical layer, persona-logic (ветераны/ВПО/возвращенцы), opportunity matching, golden dataset. **MNP Skill ID и MNP Career ID — всегда наши; Lightcast ID — только запись в mapping-таблице.**

### D. Можно ли на Lightcast построить украинский Career Transition Engine?
**Нет — на Lightcast как источнике данных для Украины нельзя** (Career Pathways API Украину не покрывает; job postings по Украине — Set 3/4, ненадёжны). **Да — на методологии Lightcast можно**, реализовав её самим на ESCO + O*NET + украинских job-бордах. Career Transition Engine — это **BUILD (наш IP)**, где Lightcast играет роль документированного эталона и (опционально) поставщика более богатых skill-профилей.

### E. Что Lightcast не закрывает для Украины?
1. Украинский спрос на профессии (кол-во вакансий, динамика, регионы).
2. Украинские зарплаты и реальный income upside перехода в гривне.
3. Реальные украинские вакансии/стажировки для opportunity matching.
4. Украинские работодатели (кроме крупнейших с англоязычными сайтами).
5. Career Pathways / feeder / next-step для украинского рынка.
6. Украинский язык (названия профессий, навыков, парсинг украинских CV) — не подтверждено, вероятно нет.
7. Украинская специфика образования/сертификаций (ОКР, дипломы, курсы ДСЗ).
8. Программы для ветеранов/ВПО и государственные ваучеры на переобучение.
9. Персонализация person→occupation (Lightcast работает occupation→occupation).

### F. Какой минимальный пилот провести?
**Внутренний пилот без Lightcast, параллельно — переговоры.**
1. **Неделя 1–2:** созвон с Lightcast, ответы на §23, запрос sandbox/nonprofit-доступа.
2. **Неделя 1–4 (параллельно):** собрать сквозной прототип §20 (Accountant → Financial Analyst) на ESCO + O*NET + ручной выгрузке work.ua/robota.ua. Замерить, что цепочка собирается на ≥75%.
3. **Неделя 4–6:** если получен доступ Lightcast — прогнать те же кейсы через Classification + Career Pathways, сравнить skill-extraction и transition-рекомендации с нашим baseline. Решение BUY/BUILD по каждому компоненту §17 — на данных, не на «красивых API».
4. **Gate:** Lightcast входит в архитектуру только там, где даёт измеримый прирост качества И лицензия/GDPR подтверждены И есть заместимый fallback.

### G. Сколько месяцев разработки экономит Lightcast?
`INFERENCE` (оценка, не факт):

| Компонент | Экономия | Комментарий |
|---|---|---|
| Skills-таксономия (tech/digital поверх ESCO) | 1–2 мес | ESCO и так покрывает базу; Lightcast экономит на digital-нише и emerging skills |
| Skill-extraction NER | 0.5–1.5 мес | Только если Classification API реально лучше нашего ESCO+LLM |
| Методология similarity / career pathways / DDN | 1.5–2.5 мес | Документация экономит R&D; реализацию всё равно пишем сами |
| Skill Gap формула + калибровка | 0.5–1 мес | Формула открыта; эталон для валидации |
| **Итого** | **~4–7 месяцев** | При условии успешного пилота и приемлемой лицензии/цены |

Без Lightcast те же результаты достижимы на ESCO/O*NET/WEF — медленнее на 4–7 месяцев и с чуть менее свежей digital-таксономией. **Lightcast — ускоритель, не разблокировщик.**

### H. Следующий конкретный шаг Founder
1. **Отправить Lightcast запрос** через «Speak with a Data Pro» с пометкой «Ukraine nonprofit / workforce recovery», приложив one-pager §24 и попросив: nonprofit-условия, sandbox-доступ к Classification + Career Pathways, созвон по §23.
2. **Параллельно** — поставить инженерам задачу собрать прототип §20 на открытых источниках (ESCO + O*NET + ручной work.ua/robota.ua), дедлайн 3–4 недели, критерий — ≥75% полей цепочки.
3. **Создать задачу DATA-002** — доступ к work.ua / robota.ua (официальный API / партнёрство / условия использования). Это более критичный для Украины источник, чем Lightcast.
4. **Не подписывать** никаких контрактов и многолетних обязательств с Lightcast до прохождения gate из §F.
5. **Занести вывод в архитектуру:** обновить [01_SYSTEM_ARCHITECTURE.md](../architecture/01_SYSTEM_ARCHITECTURE.md) и Career KB-раздел — зафиксировать принцип «MNP Skill/Career ID + mapping-слой; внешние таксономии за anti-corruption адаптерами; ни один компонент критического пути не является чистым BUY».

---

## Приложение: Источники

**Официальные Lightcast:**
- [lightcast.io — главная](https://lightcast.io/) · [Data overview](https://lightcast.io/products/data/overview) · [Our taxonomies](https://lightcast.io/products/data/our-taxonomies) · [Global Data](https://lightcast.io/products/data/global-data)
- [API menu](https://lightcast.io/our-data/api/menu) · [APIs overview](https://lightcast.io/our-data/api) · [Open Skills](https://lightcast.io/open-skills) · [Open Skills FAQ](https://lightcast.io/open-skills/faqs) · [Open Skills access](https://lightcast.io/open-skills/access)
- [Open Skills Taxonomy blog](https://lightcast.io/resources/blog/open-skills-taxonomy) · [Career Pathways launch](https://lightcast.io/resources/blog/career-pathways-launch) · [Global footprint +300%](https://lightcast.io/resources/blog/lightcast-extends-global-data-footprint-by-300percent)

**Lightcast Knowledge Base:**
- [Career Pathways](https://kb.lightcast.io/en/articles/6641056-lightcast-career-pathways) · [Similarity Model](https://kb.lightcast.io/en/articles/12101614-lightcast-similarity-model) · [Occupation Taxonomy v7](https://kb.lightcast.io/en/articles/10430137-lightcast-occupation-taxonomy-update)
- [Global Sets](https://kb.lightcast.io/en/articles/13731693-global-sets) · [Global Data 101](https://kb.lightcast.io/en/articles/7153977-global-data-101) · [Global Data Release Notes](https://kb.lightcast.io/en/articles/9252367-global-data-release-notes) · [JPA Methodology](https://kb.lightcast.io/en/articles/6957446-job-posting-analytics-jpa-methodology)

**Lightcast Developer Docs:**
- [docs.lightcast.io API index (llms.txt)](https://docs.lightcast.io/lightcast-api/llms.txt) · [Classification overview](https://docs.lightcast.io/lightcast-api/reference/overview-classification) · [Core LMI overview](https://docs.lightcast.io/lightcast-api/reference/overview-core-lmi) · [Career Pathways data](https://docs.lightcast.io/data/docs/career-pathways) · [Data shares](https://docs.lightcast.io/data/docs)
- [Career Coach API suite](https://docs.lightcast.dev/guides/career-coach-api-suite) · [Careers API](https://docs.lightcast.dev/apis/careers) · [Career Pathways API](https://docs.lightcast.dev/apis/career-pathways) · [Role Pricing API](https://docs.lightcast.dev/apis/role-pricing) · [Job Postings API](https://docs.lightcast.dev/apis/job-postings)

**Lightcast Legal:**
- [Open Terms of Use v1.2](https://legal.lightcast.io/lightcast-legal/open-terms-of-use?v=1.2) · [General Terms of Service](https://legal.lightcast.io/lightcast-legal/general-terms-of-service) · [Privacy Policy](https://legal.lightcast.io/lightcast-legal/privacy-policy)

**Внешние / проверяемые:**
- [EDCC Partnership pricing deck, Nov 2022 (PDF)](https://edcconline.org/wp-content/uploads/2022/11/EDCC-Pricing-Updated-Lightcast.pdf) — единственный найденный документ с конкретными ценами
- [World Bank — «Introduction to Lightcast Data and Skills», COLABORA, Feb 2026 (PDF)](https://thedocs.worldbank.org/en/doc/9074de6ad9bee77a6c5bee1d35ab417e-0370022026/original/COLABORA-Feb-2026-Introduction-to-Lightcast-Data-and-Skills-Matt-Walsh-ESP.pdf)
- [PR Newswire — Lightcast extends footprint +300% (10 Mar 2026)](https://www.prnewswire.com/news-releases/lightcast-extends-global-data-footprint-by-300-delivering-the-industrys-largest-global-labor-market-coverage-302708689.html)
- [PR Newswire — Lightcast 40+ countries expansion](https://www.prnewswire.com/news-releases/lightcast-expands-global-labor-data-coverage-to-more-than-40-countries-delivering-workforce-insights-for-strategic-planning-in-uncertain-times-302440592.html)
- [Dewey Data — Lightcast for academic research](https://www.deweydata.io/data-partners/lightcast)
- [Watermark Insights — passthrough Lightcast terms](https://www.watermarkinsights.com/legal/lightcast-terms/)
- [Learn & Work Ecosystem Library — Lightcast Skills Taxonomy](https://learnworkecosystemlibrary.com/initiatives/lightcast-skills-taxonomy/)

**Открытые альтернативы (для Hybrid stack):**
- ESCO — https://esco.ec.europa.eu · O*NET — https://www.onetonline.org · [ESCO–O*NET crosswalk](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/crosswalk-between-onet-and-esco)

---

*Конец DATA-001 v0.1. Блокирующие пункты для v1.0: ответы Lightcast на §23 (особенно Ukraine Set, украинский язык, лицензия на хранение derived-данных, GDPR-место обработки), результат прототипа §20, задача DATA-002 (work.ua/robota.ua).*
