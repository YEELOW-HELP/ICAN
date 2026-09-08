# MNP DEVELOPMENT PACKAGE V1

**Product:** МОЖУ: Мій Напрям  
**Purpose:** Founder-approved specification baseline for starting implementation.  
**Core:** deterministic, explainable, Ukraine-first career navigation system for adults.

## Product promise
Turn a person's existing career capital, goals and constraints into a structured Career Card, compare it against a managed Career Knowledge Base, rank realistic career transitions, expose gaps and market evidence, and build an actionable route.

## V1 non-negotiables
- Adult-first.
- CV optional; manual questionnaire alternative.
- No LLM dependency in BASIC matching flow.
- No Lightcast in V1.
- Own `MNP_CAREER_ID` and `MNP_SKILL_ID`.
- ESCO/O*NET may enrich open occupational knowledge; Ukrainian market layer is separate.
- Initial Career Universe: 50 ACTIVE careers.
- Career KB is editable/versioned; careers can be added/archived without engine changes.
- No user-facing fake probability/Match %.
- `UNKNOWN != ABSENT`.
- Fit, Feasibility, Confidence and Market are distinct.
- Result is shown immediately; no mandatory confirmation screen.
- Every material recommendation is explainable and reproducible.

## Package map
1. Foundation — concept, methodology, decisions, scope.
2. Domain — Career Card, Skills, Career Profile, Evidence.
3. Input — resume parsing and questionnaire.
4. Knowledge Base — Career KB and ETL.
5. Engine — matching, feasibility, transitions, gaps, ranking.
6. Market & Opportunities — Ukraine market, learning and actionable opportunities.
7. Product & UX — PRD, site, cabinet, report.
8. Technical — architecture, database, API, security, AI/cost guards.
9. Quality — golden dataset, evals, tests, analytics, pilot.
10. Delivery — roadmap, GitHub issue map, DoD and release gates.

## Source-of-truth order
`Methodology → Founder Decisions → Domain Schemas → Engine Specs → Data/ETL → PRD/UX → Technical Contracts → Tests/Evals`

## Ready-to-code gate
Engineering may start vertical-slice implementation when all P0 documents are versioned in the repository and the first 50-career data build has a reproducible seed pipeline.
