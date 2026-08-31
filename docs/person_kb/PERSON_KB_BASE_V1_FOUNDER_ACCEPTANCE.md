# PERSON KB BASE V1 — Founder Acceptance

Branch `person-kb-base-v1` off `product-system-v3.1`. Architecture:
`docs/person_kb/PERSON_KB_BASE_V1.md`.

## Acceptance checklist

### USER
- [ ] User sees Person Profile start (`#/profile`)
- [ ] User can choose CV
- [ ] User can choose manual profile
- [ ] User can fill basic information
- [ ] Phone saves
- [ ] Email saves
- [ ] Telegram saves (normalized: `@x` / `t.me/x` → `x`)
- [ ] Education works
- [ ] Zero work experience works (skip the Досвід step)
- [ ] Experience works (`raw_job_title` stored verbatim)
- [ ] Activities work
- [ ] Skills work (canonical search + "Додати своє")
- [ ] Languages work
- [ ] Mobility works (tri-state)
- [ ] Profile saves
- [ ] Profile reloads with the same data
- [ ] User can edit own profile (`#/profile/edit`)
- [ ] User cannot access another user's profile
- [ ] Private user routes need a **Bearer session token** (from `POST /v1/mnp/session`); a bare `X-Mnp-User-Id` is rejected (401)
- [ ] User A cannot impersonate B by supplying B's UUID with A's token

### CV
- [ ] CV uploads (.pdf / .docx / .txt)
- [ ] CV parses → candidate facts appear
- [ ] Candidate facts are editable
- [ ] Candidate facts can be rejected (uncheck)
- [ ] Candidate facts can be confirmed
- [ ] `system_detected` is NOT automatically trusted (nothing persisted before confirm)
- [ ] Confirmed facts enter Person KB (`evidence_state = user_confirmed`)
- [ ] Parser failure → "заповнити профіль вручну" fallback, file kept

### ADMIN
- [ ] Person list opens (`#/admin/persons`)
- [ ] Admin can create Person (DRAFT)
- [ ] Admin can edit Person (all BASE fields)
- [ ] Admin can add / edit / delete nested records
- [ ] Admin changes persist across reload + server restart
- [ ] Person can be archived / unarchived

### EXCEL
- [ ] Excel generates (`export-persons-excel`)
- [ ] Excel opens (openpyxl)
- [ ] Ukrainian headers
- [ ] All 11 sheets
- [ ] DB values match Excel
- [ ] Evidence state visible
- [ ] UNKNOWN shown as "Немає даних", not "Ні"

### SECURITY
- [ ] `POST /v1/mnp/session` returns a cryptographically random `session_token` (not derivable from `user_id`)
- [ ] Only the token hash is stored in `mnp_web_sessions`
- [ ] Missing / invalid token → 401 on private Person routes
- [ ] Token never echoed in error responses
- [ ] Admin auth unchanged; a Person session token does not unlock admin routes

### ARCHITECTURE
- [ ] One canonical Person KB (`MnpPerson`)
- [ ] Shared Skill universe with Career KB (`mnp_person_skills_v1 → mnp_skills`)
- [ ] No duplicate Person taxonomy
- [ ] No competing Evidence systems (per-row state, not a new polymorphic table)
- [ ] Career KB unchanged (150 / 5 ACTIVE / 145 DRAFT)
- [ ] Matching methodology unchanged
- [ ] Market KB not added

## Golden personas (synthetic, seeded by `dev_seed`)

| | Persona A — **Андрій Демо-Випускник** | Persona B — **Марина Демо-Досвідчена** |
|---|---|---|
| profile | graduate, **no formal work experience** | experienced, 2 jobs |
| education | Бакалавр, КН, ХНУ | Спеціаліст, економіка, ДНУ |
| activities | academic project + "Староста групи" | — |
| experience | — (valid path) | Керівник відділу продажів + Менеджер з продажу (raw titles verbatim) |
| credentials | — | course "Управління продажами" |
| skills | Excel, PowerPoint, Python | Ведення переговорів, CRM, Управління командою |
| languages | English B1, Українська native | English B2, Українська native |
| mobility | no licence, willing to relocate, hybrid | licence B, car, onsite |

Persona C (CV upload) — `tests/fixtures/persona_c_cv.txt`, exercised by
`test_person_kb_base_v1.py::test_cv_flow_over_http`.

## Known limitations

See `PERSON_KB_BASE_V1.md` §13/§15/§16. Headline items:

1. **Resume parser accuracy** — the deterministic parser mis-splits some
   free-form Ukrainian experience blocks (e.g. a responsibility line read
   as the job title). The CV **review screen** is the designed correction
   point; the person edits before confirm. A better parser is out of V1
   scope.
2. **Person KB is not yet wired into Matching** — `run_match` still keys
   off the old `MnpCareerCard`. A `MnpPerson → matching input` adapter is
   the next Person-domain step. Existing matching is untouched.
3. **`pending_review` custom skills** have no review UI yet — they are
   stored and visible (Excel `60_SKILLS_TOOLS`, `custom_status`), pending
   a taxonomy-review screen.
4. The old `MnpCareerCard` person stack is **retained** for matching
   compatibility (not deleted) — see disposition table.

## Acceptance status

**AWAITING FOUNDER SIGN-OFF.**
