# HUMAN CLASSIFICATION GUIDE — MNP DATA EXPLORER V1

How a methodologist hand-builds a **Person Profile**, hand-compares
**Person ↔ Career**, and records a **Human Expected Result** — the human
reference the MNP engine is checked against.

Everything is authored as **YAML**. Nothing is generated, inferred, or
AI-classified. `UNKNOWN` is expressed by **leaving a field out**, never by
writing a placeholder. Files are validated against the real MNP enums by
`data_explorer.human_lab.schema` — a bad value fails loudly.

## Where the files live

| | path | committed? |
|---|---|---|
| worked examples | `data_explorer/human_lab/examples/*.yaml` | yes |
| your working set | `data/data_explorer/human_lab/*.yaml` | no (gitignored) |

Both are picked up by `python -m data_explorer.cli golden`.

## 1. Person Profile — `<persona_id>.person.yaml`

Use the approved MNP model (`MNP_MINIMAL_QUESTIONNAIRE_V1`, Founder
Decisions #10, #27). Minimum: `persona_id`, `label`, `segment`,
`last_role`, `years_experience`, plus whatever career capital you can
state.

```yaml
persona_id: csr_to_office          # slug, stable, never reused
segment: career_changer            # experienced_professional | unemployed | career_changer | idp
                                   #  | veteran | return_to_ukraine | incomplete_cv | no_cv
                                   #  | legal_blocker | high_fit_low_confidence | transferable_skills
skills:
  - {name: "Customer Support", proficiency: strong, evidence: verified}
    # proficiency: basic | working | strong          (Founder Decision #10)
    # evidence:    claimed | inferred | verified      (Founder Decision #8)
    # a skill the person MIGHT have but you have no evidence for -> OMIT IT (that is UNKNOWN)
constraints:
  - {category: language, description: "...", hardness: soft, severity: moderate}
    # category: education | experience | credential | language | legal | other
    # hardness: soft | hard    — a HARD constraint needs authoritative evidence (Founder Decision #28)
goals: [increase_income]           # find_work | change_career | increase_income | return_to_market | explore
```

See `data_explorer/human_lab/examples/csr_to_office.person.yaml` for a full one.

## 2. Career Comparison — `<persona_id>__<career_code>.comparison.yaml` (optional working artifact)

One row per compared pair. `component` is an MNP match component;
`match_state` is `match | partial_gap | full_gap | unknown`; `source`
records where the fact came from (`ESCO | ONET | ISCO | CROSSWALK |
MNP_EDITORIAL | MNP_CALCULATION | HUMAN_JUDGEMENT | UNKNOWN`).

```yaml
persona_id: csr_to_office
career_code: sales_manager
lines:
  - component: skill_fit
    person_value: "Customer Support (strong), CRM (working)"
    career_requirement: "Sales Negotiation (must_have), B2B Sales (high_value)"
    source: MNP_EDITORIAL
    match_state: partial_gap
    human_decision: "reachable with training; sales base is the gap"
    comment: "service->sales is one progression step"
```

Market components (`market_attractiveness`, `income_potential`) are
**NOT_IN_SCOPE** for Explorer V1 — do not fill fake numbers.

## 3. Human Expected Result — `<persona_id>.expected.yaml`

The reference outcome, hand-decided against the current ACTIVE careers.

```yaml
persona_id: csr_to_office
expected_top_careers: [customer_service_representative]      # "best for me"
acceptable_careers:  [sales_manager]
unacceptable_careers: [software_developer, accountant]       # must NOT be surfaced as a fit
expected_feasibility:            # career_code -> ready_now|near_ready|reachable|long_transition|blocked
  sales_manager: reachable
expected_transition_distance:    # career_code -> d0_same_career .. d5_fundamental_retraining
  sales_manager: d1_progression
expected_gaps:
  - {skill_or_knowledge: "Sales Negotiation", gap_type: skill, classification: must_have, action: learn}
    # gap_type: skill|knowledge|experience|credential|language|proof|positioning
    # classification: must_have|high_value|differentiator|optional
    # action: learn|practice|prove|certify|reframe
expected_unknowns: ["Sales Negotiation — no evidence either way"]
expected_blockers: []            # only a proven HARD requirement belongs here
rationale: "..."
reviewer: "your name"
```

## 4. Export to a Golden fixture

```bash
python -m data_explorer.cli golden
```

Writes `evals/golden_data_explorer/case_<persona_id>.json` (+ `schema.json`).
The Golden Dataset is **versioned and never silently rewritten to make a
test pass** (`MNP_GOLDEN_DATASET_V1`). See `GOLDEN_DATASET_EXPORT.md`.

## Coverage target (`MNP_GOLDEN_DATASET_V1`)

20–50 personas across: experienced professional · unemployed · career
changer · IDP · veteran civilian transition · return-to-Ukraine ·
incomplete CV · no CV · strong credentials · legal blocker · high
fit/low confidence · transferable skills across domains.
