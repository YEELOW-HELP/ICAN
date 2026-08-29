# DATA-002 — MNP Career Data Foundation (консолидация)

> **Тип:** сводная карта источников данных Career Intelligence Engine + статус.
> **Дата:** 29 августа 2026. **Ветка:** `data-foundation-v1` (от `matching-v1-deterministic-core`).
> **Связанные документы:**
> [24_DATA-001_LIGHTCAST_TECHNICAL_DATA_DUE_DILIGENCE.md](24_DATA-001_LIGHTCAST_TECHNICAL_DATA_DUE_DILIGENCE.md),
> [20_MATCHING_V1_FOUNDER_DEFINITION.md](20_MATCHING_V1_FOUNDER_DEFINITION.md),
> `methodology_lab/06_CAREER_KB/MNP_CAREER_KB_V1.md`,
> `methodology_lab/06_CAREER_KB/MNP_WORKUA_DATA_USE_DECISION_V0.1.md`,
> [../engineering/27_MATCHING_V1_M4_6_ONET_PRODUCTION_IMPORT.md](../engineering/27_MATCHING_V1_M4_6_ONET_PRODUCTION_IMPORT.md).

---

## 1. Три слоя Career KB (решение Founder #8, `MNP_CAREER_KB_V1.md`)

| Слой | Источник | Что даёт | Статус |
|---|---|---|---|
| **A. Каталог + названия + market data** | **Work.ua** career-guide (~149 профессий UA) | UA-native названия, галузі, описания, hard/soft skills, освітні шляхи, вилка ЗП, число вакансій, тренд | 🔴 **Заблокировано** licensing-gate (`MNP_WORKUA_DATA_USE_DECISION_V0.1.md`) — ни импорта списка, ни структуры, ни контента до письменного соглашения с Work.ua |
| **B. Психометрические векторы профессий** | **O*NET** (public domain, CC BY 4.0) | RIASEC, Work Styles, Work Context, Work Values, Job Zones — числовой профиль для матчинга | 🟢 **Сделано (M4.6)** — полный импорт O*NET 31.0 + 30.2, все ~1000 профессий в reference, 23 Alpha-карьеры получили `career_vector_v0.3` |
| **C. MNP-разметка** | наша курация | корректировка векторов под UA-контекст; entry-requirements (мова, ліцензії, НМТ, легал); пометки достоверности; crosswalk-review | ⚪ curation-задача, инструменты готовы |

**Lightcast (DATA-001):** не входит в архитектуру. API подключить нельзя
(нет контракта). Роль — только **outreach-пакет** для возможного пилота
(DATA-001 §24) + заглушка-адаптер, если появится доступ. Не критический путь.

**ESCO:** рассмотрен в DATA-001, **не выбран** (Founder выбрал Work.ua + O*NET).
Остаётся documented extension point на случай, если понадобится
украиноязычный слой названий навыков/профессий.

---

## 2. Карта: какой источник питает какой выход матчинга

Выходы матчинга V1 (`20_MATCHING_V1_FOUNDER_DEFINITION.md` §4):
Interest Fit / Work Style Fit / Values Fit / Transition Feasibility / Coverage.

| Выход | Career-сторона | Источник | Статус для 23 Alpha |
|---|---|---|---|
| **Interest Fit** | RIASEC-вектор профессии | O*NET 31.0 `OI` | 🟢 23/23, реальные числа |
| **Work Style Fit** | Work Styles importance | O*NET 31.0 `WI` (4 ключа: leadership, initiative, ambiguity_tolerance, collaboration) | 🟢 23/23 (данные есть); ⚠️ матчинг часто `low_differentiation` — см. doc 27 §5/§7 |
| **Values Fit** | Work Values importance | O*NET 30.2 `EX` (3 DIRECT-ключа) | 🟡 20/23; 5 из 8 MNP-ключей O*NET не покрывает вообще |
| **Transition Feasibility** | education / credential / job-zone / work-format | O*NET Job Zone + Stage 3A `CareerRequirement`/`CareerWorkContext` | 🟢 job-zone 23/23; requirements — Stage 3A scope (14/24 careers) |
| **Labour-market indicators** (отдельный блок, не fit) | вилка ЗП, вакансии, тренд по Украине | **Work.ua / robota.ua / ДСЗ** | 🔴 нет — Work.ua под gate; robota.ua/ДСЗ = отдельная задача **DATA-003** |
| Ukrainian названия профессий/навыков | — | Work.ua (gate) / КП України / ESCP uk | 🟡 сейчас английские O*NET-названия + украинские из Stage 3A curated seed |

---

## 3. Что сделано в M4.6 (эта ветка)

- **Пайплайн импорта O*NET** (`scripts/onet_import/`): download → parse →
  `data/onet/onet_reference.sqlite` (1016 профессий) → scoped
  `app/services/career_kb/onet_source_v3.json` (23 SOC, ~28 КБ, коммитится).
  Идемпотентно, оффлайн, zero-AI, воспроизводимо.
- **`career_vector_v0.3`** (`app/services/career_kb/seed_v3.py`): новые
  версионированные `CareerMatchingProfile` из реального O*NET, через
  неизменённые M3-гейты. `v0.1`/`v0.2` остались immutable.
- **Закрыты gap'ы M4.5:** Work Style 1→23 карьеры, Work Values 0→20,
  RIASEC approximation→реальные числа.
- **Crosswalk-движок** (`suggest_crosswalk.py`): проверяет/расширяет ручной
  crosswalk (18/23 совпадают), масштабируется на ~149 когда каталог появится.
- **Атрибуция** O*NET CC BY 4.0 (`data/onet/ATTRIBUTION.md` + `KnowledgeSource`).
- Миграции нет (чистый data-bump), движок не тронут, 0 регрессий.

---

## 4. Что заблокировано / не сделано (честный список)

| Блок | Причина | Кто снимает |
|---|---|---|
| Каталог ~149 профессий (Work.ua) | Licensing-gate — Work.ua не лицензировал контент/структуру | **Founder / бизнес-контакт** инициирует разговор с Work.ua (`MNP_WORKUA_DATA_USE_DECISION_V0.1.md` §D) |
| Украинский рынок труда: спрос, ЗП, вакансии | Lightcast Set 3/4 не годится (DATA-001 §3); Work.ua под gate | **DATA-003**: work.ua / robota.ua / OLX / ДСЗ — доступ по API/соглашению |
| 5 из 8 MNP Work Values (income, stability, growth, work_life_balance, learning) | нет аналога в O*NET | MNP-курация (слой C) |
| Work Style / Values Fit реально SCORED | user-side fixture-ограничение + низкая вариативность O*NET WI на 4 элементах | **M5 методология**: per-item ответы в фикстурах + решение по differentiation-guard для коротких векторов |
| Украиноязычные названия O*NET-профессий | O*NET только английский | слой C (курация) или ESCO uk (extension point) |
| Lightcast данные | нет контракта | Founder отправляет outreach-пакет DATA-001 §24; PILOT FIRST |

---

## 5. Следующие шаги (по приоритету)

1. **DATA-003** — доступ к work.ua / robota.ua / ДСЗ. Для украинского
   продукта критичнее Lightcast и O*NET-обогащения. Отдельная задача.
2. **Work.ua licensing-разговор** — Founder / бизнес. Разблокирует слой A
   (каталог ~149 + market data).
3. **M5 методология** — per-item ответы в тестовых фикстурах; решение по
   differentiation-guard; sourcing-план для 5 MNP-only Work Values.
4. **Lightcast outreach** — отправить DATA-001 §24 one-pager (nonprofit /
   Ukraine workforce recovery). Не блокирует ничего, PILOT FIRST.
5. **Промоушен `career_vector_v0.3` в основную ветку** — по Founder GO,
   после M5-решений (сейчас `data-foundation-v1`, PR открыт, не смёржен).

---

## 6. Архитектурные инварианты (соблюдены, не меняются)

- `Career.code` — единственный внутренний бизнес-ключ. O*NET-SOC / Work.ua
  slug / ESCO URI — только в `CareerExternalMapping` (crosswalk), никогда
  не первичный ключ.
- Векторы версионируются; смена версии O*NET = новый `career_vector_v*` +
  новые `CareerMatchingProfile`, старые immutable.
- `UNKNOWN ≠ 0`: отсутствие O*NET-данных = отсутствующий компонент, не
  сфабрикованный ноль.
- Zero-AI: ни один модуль career-vector пайплайна не вызывает AI Gateway.
- PROFILE_ONLY шкала никогда не получает career-side компонент (гейт в
  `vectors.add_career_matching_component`).
- Market-sensitive факты (ЗП, вакансии) — `CareerFact.is_market_sensitive`
  + `source_id` + `expires_at`, отдельным блоком, никогда не в fit-балл.
