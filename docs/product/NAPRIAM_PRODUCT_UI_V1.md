# NAPRIAM Product UI V1 — screen map & state

Branch `person-kb-base-v1` · PR #25 · **not merged**. Companion to
`docs/person_kb/PERSON_KB_BASE_V1.md` §17.

The **whole** NAPRIAM product is laid out visually now; functionality is
activated phase-by-phase. Every screen below is one of:

* **FUNCTIONAL NOW** — works end-to-end against real data.
* **VISUAL / FUTURE** — rendered in the real design system, controls
  disabled and marked `«Незабаром»`, no navigation to nowhere, **no
  fabricated numbers**.
* **NOT IMPLEMENTED** — not present in the UI at all yet.

Frontend: `mnp_frontend/` (plain JS, hash router, no build step).
`app.js` = public + routing, `person.js` = Person KB flows, `workspace.js`
= post-profile career workspace, `admin.js` = internal admin.

### Interaction rules (frozen for Founder Acceptance)

* **Every control** is WORKING, FUTURE (`disabled` + `«Незабаром»`), or
  DEMO (`«Приклад»`). No control that looks active but does nothing,
  blanks the page, throws, misroutes, or leaks an `/admin` route.
* **One primary CTA per screen** (blue `.btn`); everything else is
  `.btn.secondary` / `.btn.ghost`.
* **Header** shows a single action: `Створити профіль` until a profile
  exists (`localStorage.mnp_has_profile`), then `Мій профіль` → `#/app`.
  A fresh session clears the flag.
* **No internal terms in customer copy** — no "Person KB", "Career KB",
  "MnpPerson", "taxonomy", "methodology", "Founder", "skill gap",
  "детермінований". Evidence shows friendly labels only
  (`Знайдено у CV` / `Підтверджено`); a hand-typed fact shows no chip.
* **Empty vs future vs demo** — `«Поки що тут нічого немає»` /
  `«Незабаром»` / `«Приклад»`, never "у вас немає відповідних…" for a
  feature that simply isn't built.

---

## Two customer states, one design system

| state | chrome | routes |
|---|---|---|
| **A — before profile** | public header (`#site-header`) | `#/`, `#/how`, `#/about`, `#/login`, `#/pricing`, `#/catalog`, `#/opportunities`, `#/profile…` |
| **B — after profile** | workspace shell (left sidebar + slim top bar), no public header, no admin links | `#/app`, `#/app/<module>` |

Workspace left navigation (Founder-approved; icons are inline SVG from
`ui.js`, not emoji). Future modules keep a sidebar entry — they open a
real explainer / future-state screen — with a `Незабаром` pill:

```
Огляд · Мій профіль
Мої сценарії [Незабаром] · Що зміниться, якщо… [Незабаром] · Мій маршрут [Незабаром]
План дій [Незабаром] · Прогрес [Незабаром] · Інсайти [Незабаром]
Вакансії [Незабаром] · Ресурси [Незабаром]
── AI Коуч [Premium] · Консультація [Незабаром] · Тарифи
```

The Digital Career Profile detail screens (`#/app/skills`,
`#/app/strengths`, `#/app/values`, `#/app/goals`) are reached from
**Мій профіль**, not the sidebar.

Admin (`#/admin/*`) is a **separate** plain internal interface with its
own dark top nav (`NAPRIAM ADMIN · Люди · Професії · Вийти`), rendered
into `#site-header` — never blended with the customer UI, never linked
from customer navigation.

---

## Screen map

### PUBLIC

| screen | route | state |
|---|---|---|
| Home | `#/` | **FUNCTIONAL** — hero, CV drop-zone, manual entry; result preview marked «Приклад результату» |
| How it works | `#/how` | **FUNCTIONAL** — 4 conceptual steps, no metrics |
| About | `#/about` | **FUNCTIONAL** — mission only |
| Login | `#/login` | **VISUAL / FUTURE** — Email/Password/Google/LinkedIn all disabled `«Незабаром»` |
| Pricing | `#/pricing` | **VISUAL / FUTURE** — Free (available) / Premium / Premium + Coach; prices are placeholders, no checkout |
| Create profile | `#/profile` | **FUNCTIONAL** — CV + manual; LinkedIn card disabled `«Незабаром»` |
| CV upload / parse / review | `#/profile/cv` | **FUNCTIONAL** — real parser; failure keeps file + manual fallback |
| Manual profile (8-step) | `#/profile/build` | **FUNCTIONAL** |
| Confirmation | `#/profile/confirmed` | **FUNCTIONAL** — «Ми проаналізували ваш досвід», friendly evidence labels |

### PROFILE — Digital Career Profile (I CAN / I AM / I WANT)

**One `MnpPerson`, three projections.** No new tables, no `MnpPerson`
duplicate, no invented fields. Later these feed Matching (§ Future
contract).

| screen | route | state |
|---|---|---|
| Digital Profile home | `#/app/profile` | **FUNCTIONAL** — three cards (Я можу / Я є / Я хочу) with deterministic completeness state, the `I CAN + I AM + I WANT → точніші сценарії` visual, future-state card for personal scenarios |
| **I CAN** — My Profile (read-only) | `#/profile/me` | **FUNCTIONAL** — human-readable canonical `MnpPerson` (experience · education · skills · tools · languages · projects · credentials · evidence) |
| Edit profile (tabbed) | `#/profile/edit` | **FUNCTIONAL** |
| **I CAN** — Мої навички | `#/app/skills` | **PARTIAL** — real confirmed skills FUNCTIONAL; "яких навичок бракує" block VISUAL / FUTURE |
| **I AM** — Дізнайтесь свої сильні сторони | `#/app/strengths` | **VISUAL / FUTURE** — «Пройти тест» button **disabled** + «Незабаром»; example result sections all marked «Приклад»; nothing persisted, no scoring |
| **I AM** — `#/app/assessment` | redirect | legacy route → redirects to `#/app/strengths` (the assessment is not built) |
| **I AM** — Інтереси та цінності | `#/app/values` | **VISUAL / FUTURE** — Інтереси / Цінності / Мотивація / Робочі уподобання chips |
| **I WANT** — Цілі | `#/app/goals` | **PARTIAL** — FUNCTIONAL: work format · willing-to-relocate · work geography (saved to `MnpPerson` via `POST /me/person`, the existing endpoint). VISUAL / FUTURE: desired income (goal, not market), transition pace, career directions, priority ranking |

**Completeness rule (deterministic, qualitative — no fabricated %):**

| projection | «Заповнено» | «Частково» | «Не заповнено» |
|---|---|---|---|
| I CAN | ≥3 non-empty factual sections (experience/education/skills/languages/activities/credentials) | 1–2 | 0 |
| I AM | (assessment layer not built) | — | always, for now |
| I WANT | ≥2 of {work_format≠unknown, willing_to_relocate≠unknown, work_geography non-empty} | 1 | 0 |

Combined = «Заповнено» iff all three are; «Частково» if any is non-empty;
else «Не заповнено». `mnp_frontend/workspace.js` → `iCanState` /
`iAmState` / `iWantState`.

### CAREERS

| screen | route | state |
|---|---|---|
| Професії (catalog) | `#/catalog` | **FUNCTIONAL** — ACTIVE careers only, NAPRIAM cards, no personalized %, no salary |
| Career detail | `#/catalog/{id}` | **FUNCTIONAL** — real Career KB; market section → «Дані ринку будуть додані пізніше» |
| Можливості | `#/opportunities` | **VISUAL / FUTURE** — honest empty state, routes to catalog |

### CAREER DEVELOPMENT (workspace)

| screen | route | state |
|---|---|---|
| Головна / Dashboard | `#/app` | **VISUAL / FUTURE** — «Наступна найкраща дія» hero + scenario/route/weekly/progress summaries, all `«Незабаром»` / empty |
| Сценарії | `#/app/scenarios` | **VISUAL / FUTURE** — 3 scenario types + Career Mobility Score placeholder (`«Незабаром»`, no 72/100) |
| Що, якщо? | `#/app/whatif` | **VISUAL / FUTURE** — disabled change chips, no `+%` / new-career output |
| Маршрут | `#/app/route` | **VISUAL / FUTURE** |
| План дій | `#/app/plan` | **VISUAL / FUTURE** — metric cards (0/—), Week 1–2… timeline, future task table |
| Прогрес | `#/app/progress` | **VISUAL / FUTURE** — ProgressRing 0%, streak 0, future charts |
| Щотижневий апдейт / Інсайти | `#/app/insights` | **VISUAL / FUTURE** — clearly-labelled empty state |
| Вакансії для мене | `#/app/vacancies` | **VISUAL / FUTURE** — Market KB not connected, no fake vacancies |

### SUPPORT

| screen | route | state |
|---|---|---|
| Ресурси | `#/app/resources` | **VISUAL / FUTURE** — Курси/Статті/Шаблони/Тести placeholders |
| Коуч поруч | `#/app/coach` | **VISUAL / FUTURE** — Premium; Чат/Сесії/Нотатки/Питання tabs disabled |
| Заплануйте консультацію | `#/app/consultation` | **VISUAL / FUTURE** — calendar/booking disabled |

### COMMERCIAL

| screen | route | state |
|---|---|---|
| Pricing / Premium | `#/pricing` | **VISUAL / FUTURE** — see PUBLIC |
| Payments / checkout | — | **NOT IMPLEMENTED** |

### ADMIN (separate internal interface)

| screen | route | state |
|---|---|---|
| Admin login | `#/admin/login` | **FUNCTIONAL** |
| Person KB (list / card / CRUD / archive) | `#/admin/persons…` | **FUNCTIONAL** |
| Career KB editor (all 150, all statuses) | `#/admin/catalog…` | **FUNCTIONAL** |
| Future admin modules (Dashboard · Skills · Matching · Routes · Resources · Users · Consultations · Payments · Settings) | — | **NOT IMPLEMENTED** — documented target only |

---

## Career KB scope rule (§2 / §24)

`MnpCareer.status` is a **publication** flag, **not** a query gate.

| scope | careers shown | code path |
|---|---|---|
| PUBLIC catalog `/v1/mnp/careers` | ACTIVE only | `list_active_careers` (`status == ACTIVE`) |
| PUBLIC detail `/v1/mnp/careers/{id}` | ACTIVE only (else 404) | `get_career_detail_by_id` |
| ADMIN catalog `/v1/mnp/admin/careers` | every career, every status (150) | `admin_list_careers` |
| internal Matching development | **may use all 150** | no implicit status filter on the model |

* DRAFT careers stay editable in Admin and may participate in internal
  Matching development / tests. They are **never** presented publicly as a
  published Career page.
* Career status is **never changed automatically**.
* Regression: `tests/test_career_public_scope.py` (4 tests) proves the
  three scopes are not confused.

Conceptually: `publication_status` (drives the public site) is distinct
from `matching_eligibility_for_internal_development` (all careers). V1
does not add a separate column — the single `status` enum + the query
discipline above is sufficient; a dedicated flag is only worth adding if
internal Matching later needs to *exclude* specific careers.

---

## Design system (§21 / §23)

Tokens in `style.css :root` — `--surface`, `--surface-soft`, `--text`,
`--muted`, `--primary`, `--primary-hover`, `--border`, `--success`,
`--future` (+ the original `--fg`/`--accent`/… kept as aliases),
`--space-1..5`, `--radius`, `--shadow-sm`/`-md`. Max content width
`--maxw: 1200px`.

**Icons** — inline SVG set in `ui.js` (`NvUI.icon(name)`), 20×20,
`stroke: currentColor`. No emoji in primary UI. `NvUI.greeting()` gives
the time-of-day greeting.

Shared classes:

* semantic status: `.chip--green` (have / done / strength) · `.chip--orange`
  (gap) · `.chip--red` (blocker) · `.chip--blue` (current / next / nav) ·
  `.chip--purple` (future / destination / Premium)
* `.page-header` · `.nv-ico-box` (icon tile) · `.metric-card` ·
  `.progress-ring` · `.timeline` · `.empty-state` · `.future-state`
  (+ `.soon-tag`) · `.demo-flag` · `.flow-steps` (numbered onboarding
  stepper)
* buttons: `.btn` / `.btn.secondary` / `.btn.ghost` / `.btn.is-disabled`
  (+ native `[disabled]`)
* public: `.nv-header` (single sticky row: brand · nav · actions) ·
  `.nv-hero` · `.nv-card` · `.nv-panel` · `.nv-prof-card` · `.site-footer`
* workspace: `.ws` · `.ws-side` / `.ws-nav` (icon · label · `.soon` pill) ·
  `.ws-top` · `.ws-body` · `.ws-hero` · `.dim-row` · `.chat-panel` ·
  `.plan-board`
* admin: `.adm-nav` (dark internal top bar)

CV / onboarding flow indicator: `1 Завантаження · 2 Перевірка ·
3 Підтвердження · 4 Профіль`. Manual wizard: 9 steps
(`Основне · Досвід · Освіта · Навички · Мови · Сертифікати · Активності ·
Мобільність · Перевірка`), «Крок X з 9», «Назад» / «Продовжити».

Copy is deliberately tighter than the reference screens: one main question
per screen, one primary CTA, 1–2 secondary, no long instructional
paragraphs.

---

## Future Matching contract (documented only — not implemented)

The Digital Career Profile is the input side of Matching. When Matching is
built (a separate Founder-approved task, not this PR):

| dimension | source |
|---|---|
| **Capability Fit** | I CAN — factual Person KB (experience / skills / education / credentials) |
| **Personal Fit** | I AM — assessment signal + Person evidence |
| **Goal Fit** | I WANT — canonical want-fields + the future goal layer |
| Transition Distance | (later) Person ↔ Career distance |
| Market Opportunity | (later) Market KB — not built |

Career "superpowers" (`#/app/strengths`) will later combine the assessment
signal with real Person evidence (e.g. *«Переконувати та домовлятися»* ←
assessment + sales experience + negotiation evidence). No inference logic
exists yet.

This PR does **not** implement or modify matching methodology.

## No fabricated data (§25)

Nowhere in the UI: match %, salary, demand, transition time, Career
Mobility Score, skill-improvement %, user counts, accuracy, reviews,
vacancies, employers, payments. Demo visuals carry a `«Приклад»` /
`.demo-flag` / `«Незабаром»` marker.
