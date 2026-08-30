# MNP PRODUCT MOAT AND POSITIONING V1

**Project:** МОЖУ: Мій Напрям  
**Status:** Founder Strategy / Product North Star  
**Version:** V1  
**Date:** 2026-08-30

## 1. Purpose

«Мій Напрям» is not a job board, a classic career-orientation test, a profession directory, or a generic AI career chatbot.

The core user problem is:

> **«Я не розумію, що мені робити далі в кар'єрі з урахуванням того, хто я, що вже вмію і що реально відбувається на ринку праці».**

Primary audiences include people who lost work, want to change career or increase income, need retraining, face AI/automation-driven change, veterans returning to civilian life, IDPs, Ukrainians considering return from abroad, and young adults entering the labour market.

## 2. Product positioning

### We are NOT

- a career-test website;
- another profession test;
- another Work.ua;
- an AI that simply recommends a profession.

### We ARE

# **Персональна система кар'єрної навігації України**

The product should move the user through:

> **Зрозумій, що ти вже маєш → побач, що тобі доступно → порівняй можливості → зрозумій, чого не вистачає → обери маршрут → почни діяти.**

## 3. Core product formula

MNP is built around three independent knowledge layers:

1. **PERSON KB** — what we know about the person.
2. **CAREER KB** — what we know about careers.
3. **MARKET KB UKRAINE** — what is happening with those careers in the Ukrainian labour market now.

Between them operates the MNP Decision / Matching / Transition Engine:

**PERSON × CAREER × MARKET → NEXT BEST CAREER ACTION**

## 4. Person KB

Person KB is not merely a CV. It is a structured model of a person's career capital.

It should progressively contain:

- Experience: employers, roles, duration, responsibilities, achievements, industries.
- Skills: hard skills, soft skills, tools, technologies, proficiency, evidence, confidence.
- Knowledge.
- Education: formal education, specialties, additional learning, certificates, licences.
- Languages and levels.
- Preferences.
- Work Style / Interests / Values only where methodologically justified.
- Constraints: geography, schedule, mobility, learning capacity, licensing and other real barriers.
- Goals: employment, income growth, career change, remote work, relocation, return to Ukraine, etc.

## 5. Career KB

Career KB is MNP's own structured knowledge base.

No external classifier is the MNP Career KB.

The central entity is **MNP Career**. Each career receives a structured digital profile containing at minimum:

- Identity: name, aliases, category, external IDs.
- Description.
- Responsibilities.
- Skills: hard and soft.
- Knowledge.
- Requirements: education, experience, language, licences, certificates and other hard requirements.
- Entry: whether entry without experience is possible and transition difficulty.
- Work characteristics.
- Typical career path.
- Related careers.
- Advantages/disadvantages as an MNP editorial layer.
- Provenance for material claims.

## 6. Ukrainian profession classifier

The Ukrainian profession classifier is an **official reference / identity layer**.

> **Класифікатор професій України ≠ MNP Career KB.**

MNP may present, group or clarify careers in a more useful form for career navigation while preserving links to official entities.

## 7. ESCO role

ESCO is a reference/enrichment layer, useful primarily for:

- occupation taxonomy;
- skill taxonomy;
- occupation ↔ skill relations;
- essential/optional skills;
- alternative labels;
- European interoperability.

ESCO may help populate and validate an MNP Career but does not define it automatically.

## 8. O*NET role

O*NET is primarily an occupational research layer for:

- Interests;
- Work Styles;
- Knowledge;
- Abilities;
- Work Activities;
- Work Context;
- Tasks;
- other occupational characteristics.

US salaries, employment outlook and other US market assumptions must not be automatically transferred to Ukraine.

## 9. Market KB Ukraine

Market KB answers not «What is an accountant?» but:

> **«Що відбувається з професією бухгалтера в Україні зараз?»**

Core relationship:

**Career × Vacancy × Employer × Skill × Salary × Location × Date**

It should progressively contain active/new vacancies, unique employers, requirements, skills, experience/education requirements, salary observations, work format, employment type, geography, dynamics and history.

## 10. Geography

Long-term geography:

**Ukraine → Oblast → Raion → Hromada → Settlement**

Market KB MVP starts with Kyiv and the available oblast centres, then expands to hromadas where data quality permits.

## 11. User result

MNP must not stop at «This profession suits you».

It must answer:

1. What careers are realistically accessible to me?
2. Why?
3. What am I missing?
4. How difficult is the transition?
5. How long might it take, when evidence supports a range/category?
6. Is there real demand?
7. Where is that demand?
8. What does the Ukrainian market pay?
9. What should I learn?
10. What should I do next?

## 12. Career Transition Graph

A central potential moat is not only **Person → Career**, but **Career → Career**.

For each transition MNP should eventually understand:

**shared skills + transferable experience + missing skills + hard barriers + market attractiveness.**

The user should see a space of realistic career transitions, not a single static recommendation.

## 13. Relationship to Work.ua

Work.ua is a major Ukrainian reference/competitor in vacancies and labour-market information.

Its core strength is approximately:

> **«Я знаю, яку роботу шукаю → покажіть вакансії».**

MNP must win earlier in the journey:

> **«Я не знаю, ким мені тепер працювати → допоможіть прийняти рішення».**

Conceptual boundary:

- **Work.ua:** Career/Vacancy → Job Search.
- **MNP:** Person → Career Decision → Transition → Action.

Work.ua may therefore be simultaneously a competitor, data/market reference, outbound destination and potential partner.

## 14. What we deliberately do not build

We do not:

- build a job board merely to compete with Work.ua/Robota.ua;
- copy vacancies without product need and legal/data rights;
- build another psychological test;
- build a generic AI career chatbot;
- make LLM usage the core decision mechanism where deterministic methods work;
- treat AI, UI or a mobile app as the moat;
- cover thousands of careers before validating quality;
- create material data without provenance;
- convert missing data into zero/false;
- present false precision.

## 15. AI is not the moat

LLMs are available to every competitor. AI is a tool, not MNP's defensibility.

Core V1 calculations should remain deterministic. LLMs may later assist with CV/free-text extraction, explanations, conversational UX and coaching, but should not be the sole source of career decisions.

## 16. Primary Data Moat: Person × Career × Market History

A major long-term asset is historical Ukrainian labour-market data.

Regularly preserving normalized observations of:

**Career × Location × Vacancy × Employer × Skills × Salary × Date**

can allow MNP to identify:

- growing/declining careers;
- salary change;
- emerging/disappearing skills;
- regional shifts;
- hiring trends;
- entry-level availability;
- changing requirements;
- AI-related transformation.

Interfaces can be copied. Historical datasets cannot be recreated retroactively.

## 17. Second Data Moat: Career Transition Outcomes

Over time MNP should measure outcomes, not only recommendations:

**Person Profile → Recommendation → Route → Action → Employment Outcome**

This creates evidence about which career transitions actually work for Ukrainians.

## 18. Third Data Moat: Ukrainian Career Opportunity Graph

Long-term graph:

**Person ↔ Skill ↔ Career ↔ Vacancy ↔ Employer ↔ Education ↔ Location**

This evolves MNP from a test into a Career Opportunity Graph for Ukraine.

## 19. Education Layer

Education is not a generic course catalogue.

Correct logic:

**Career Target → Personal Gap → Required Skill → Relevant Learning Opportunity**

Potential sources include universities, colleges, vocational education, courses, employment-service vouchers, employer training and grant programmes.

## 20. Opportunity Layer

After Person + Career + Market are stable, MNP can surface personalized opportunities such as vacancies, internships, learning, grants, veteran/IDP programmes, return programmes, employers and career consultants.

## 21. Return to Ukraine

A strategic use case is a Ukrainian abroad considering return.

The user should be able to select a target Ukrainian location and understand accessible careers, employers, vacancies, salaries, skills in demand, work format, gaps, pre-return learning and potential pre-return interviews.

MNP does not try to replace foreign job centres. Its territory is the person's career opportunity in Ukraine.

## 22. Why a large job board does not invalidate the strategy

A large job board can copy individual MNP features. Defensibility therefore cannot depend on one feature.

It should emerge from the integrated system:

**Person KB + Career KB + Transition Graph + Market KB + Historical Data + Outcomes + Opportunity Layer.**

The strategic goal is to become sufficiently specialized in Career Decision/Transition that integration, partnership or acquisition may be more attractive than rebuilding the full layer independently.

## 23. Partnership strategy

Work.ua, Robota.ua, education platforms, universities, the State Employment Service, Diia, employers and other institutions should not automatically be treated only as competitors.

MNP can become a decision layer between the person and existing infrastructure:

**MNP determines direction → education partner closes a gap → job platform surfaces vacancies → employer hires → MNP records outcome.**

## 24. Competitive advantages

### Early-stage advantages

- Speed.
- Focus.
- Better user experience.
- Transition-oriented matching.

These are temporary.

### Target durable advantages

1. Person Career Graph.
2. MNP Career Knowledge Base.
3. Transition Engine.
4. Ukrainian Market Intelligence.
5. Historical Market Dataset.
6. Career Transition Outcome Dataset.
7. Distribution through foundations, employment centres, employers, hromadas, veteran/IDP organisations, education and B2C.

## 25. Product North Star metric

The product should not ultimately optimize for test completions, registrations or profession-page views.

The long-term North Star should relate to **Successful Career Transitions**.

Until enough outcome data exist, use an intermediate funnel:

**Career Card completed → Career options discovered → Target career selected → Route started → Interview → Employment / Income improvement.**

## 26. Development sequence

### PHASE 1 — CAREER KB V1

5 careers.

**DB → API → Website → Excel → Founder Acceptance.**

### PHASE 2 — PERSON KB V1

Structured digital person profile.

**DB → Website → Matching → Excel → Founder Acceptance.**

### PHASE 3 — MATCHING / TRANSITION VALIDATION

**Person KB ↔ Career KB** with Human Expected Result ↔ Engine Result and Golden Dataset validation.

### PHASE 4 — MARKET KB UKRAINE

Start with Kyiv + available oblast centres.

**Career × Location × Vacancy × Salary × Employer × Skills × Date.**

Begin accumulating history as early as legally and technically possible.

### PHASE 5 — OPPORTUNITY / ACTION LAYER

Vacancies + Education + Programmes + Employers.

### PHASE 6 — SCALE

**5 → 50 → 500+ careers** and **oblast centres → hromadas of Ukraine**.

## 27. Not P0 now

Before the first four phases are validated, these are not P0:

- native mobile application;
- complex AI agent;
- social network;
- own full job board;
- thousands of careers;
- international expansion;
- complex gamification;
- full education marketplace.

## 28. Founder decision rule

For every new feature ask:

> **Does this help the person make a better career decision or execute the next step?**

For every new dataset ask:

> **Does this materially improve the Person, Career, Market or Transition model?**

If not, it is not P0.

## 29. Product North Star statement

The target system should be able to tell a person:

> **Ось що ти вже вмієш.**  
> **Ось професії, до яких ти найближче.**  
> **Ось чому вони тобі доступні.**  
> **Ось чого тобі не вистачає.**  
> **Ось де на ці професії є попит.**  
> **Ось скільки там платять.**  
> **Ось що потрібно вивчити.**  
> **Ось реальні можливості.**  
> **Ось твій наступний крок.**

The core question is not only **«Ким мені бути?»** but **«Що мені робити далі?»**

## 30. Target architecture

```text
                    MNP

               PERSON KB
                   │
                   ▼
          MATCHING / TRANSITION
                   │
                   ▼
               CAREER KB
                   │
                   ▼
          MARKET KB UKRAINE
                   │
                   ▼
             OPPORTUNITIES
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
      WORK      EDUCATION   EMPLOYERS
        │          │          │
        └──────────┼──────────┘
                   ▼
                OUTCOME
                   │
                   ▼
          CAREER HISTORY DATA
```

## 31. Strategic principle

> **MNP does not need to own every part of the career market. MNP must become the best system for understanding which next opportunity fits a specific person, why, and what they should do next.**

---

## Document governance

This document is a **Founder / Product Source of Truth** for product positioning, moat, strategic boundaries and development sequence.

It does **not** replace the approved matching methodology, domain model, API contracts or engineering Definition of Done. Where implementation detail is concerned, the canonical methodology/architecture documents remain authoritative.
