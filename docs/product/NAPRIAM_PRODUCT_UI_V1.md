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

---

## Two customer states, one design system

| state | chrome | routes |
|---|---|---|
| **A — before profile** | public header (`#site-header`) | `#/`, `#/how`, `#/about`, `#/login`, `#/pricing`, `#/catalog`, `#/opportunities`, `#/profile…` |
| **B — after profile** | workspace shell (left sidebar + slim top bar), no public header, no admin links | `#/app`, `#/app/<module>` |

Admin (`#/admin/*`) is a **separate** plain internal interface — never
blended with the customer UI, never linked from customer navigation.

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

### PROFILE

| screen | route | state |
|---|---|---|
| My Profile (read-only) | `#/profile/me` · `#/app/profile` | **FUNCTIONAL** — human-readable canonical `MnpPerson` |
| Edit profile (tabbed) | `#/profile/edit` | **FUNCTIONAL** |
| Мої навички | `#/app/skills` | **PARTIAL** — real confirmed skills list FUNCTIONAL; skill-gap block VISUAL / FUTURE |

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

## Design system (§21)

Shared classes in `style.css`:

* semantic status: `.chip--green` (have / done / strength) · `.chip--orange`
  (gap) · `.chip--red` (blocker) · `.chip--blue` (current / next / nav) ·
  `.chip--purple` (future / destination / Premium)
* `.page-header` · `.metric-card` / `.metric-grid` · `.progress-ring`
  (conic-gradient, `--p`) · `.timeline` · `.empty-state` ·
  `.future-state` (+ `.soon-tag`) · `.demo-flag`
* buttons: `.btn` / `.btn.secondary` / `.btn.ghost` / `.btn.is-disabled`
  (+ `[disabled]`)
* public: `.nv-header` · `.nv-hero` · `.nv-card` · `.nv-step` · `.nv-panel`
  · `.nv-prof-card`
* workspace: `.ws` · `.ws-side` / `.ws-nav` · `.ws-top` · `.ws-body` ·
  `.ws-hero` · `.ws-grid2`

Copy is deliberately tighter than the reference screens: one main question
per screen, one primary CTA, 1–2 secondary, no long instructional
paragraphs.

---

## No fabricated data (§25)

Nowhere in the UI: match %, salary, demand, transition time, Career
Mobility Score, skill-improvement %, user counts, accuracy, reviews,
vacancies, employers, payments. Demo visuals carry a `«Приклад»` /
`.demo-flag` / `«Незабаром»` marker.
