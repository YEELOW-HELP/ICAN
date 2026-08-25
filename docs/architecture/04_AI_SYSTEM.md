# AI System v3.1

## Goal

AI must improve personalization without becoming an unauditable source of invented facts. The platform uses deterministic services, retrieval and versioned LLM calls together.

## Components

1. **Interview Orchestrator** — chooses the next best question based on missing evidence and confidence.
2. **Evidence Extractor** — extracts facts from answers/CV into structured evidence.
3. **Profile Synthesizer** — creates claims with evidence links and confidence.
4. **Career Retriever** — retrieves candidate careers from Career Knowledge Graph.
5. **Scenario Ranker** — applies hard constraints and multi-factor scoring.
6. **Narrative Generator** — turns structured results into clear user-facing text.
7. **Roadmap Planner** — generates milestones/tasks from direction + gaps + constraints.
8. **Opportunity Matcher** — ranks verified opportunities.
9. **Mentor** — conversational layer with explicit tools/actions.
10. **Guide Copilot** — session prep, drafts, summaries and QA prompts.
11. **QA Critic** — checks contradictions, evidence gaps and hallucinated facts.

## AI Gateway

Every model call goes through one gateway with:
- task name;
- provider/model;
- prompt version;
- structured output schema;
- temperature/settings;
- trace id;
- input/output token count;
- latency;
- estimated cost;
- retry/fallback;
- safety outcome.

No business service calls an LLM provider directly.

The per-call fields above are the target shape of `AI_TRACE`
(`docs/architecture/02_ERD.md`) — its future persistent representation. As
of Sprint 0 Part 4, `app/ai_gateway.py` already emits this data as
structured logs on every call, success and failure, for the one AI task
that exists today (`legacy-screening-v1`); it is not persisted to a table
yet, and retry/fallback are not implemented yet.

## Structured output rule

LLMs return schema-valid JSON first. UI text is rendered from structured objects. Invalid output is retried or rejected; it is never shown directly.

## Profile claim example

```json
{
  "claim_key": "strength.systems_thinking",
  "label": "Системне мислення",
  "score": 0.82,
  "confidence": 0.76,
  "evidence_ids": ["ev_1", "ev_8", "ev_11"],
  "status": "hypothesis",
  "model_version": "profile-synth-v1"
}
```

## Recommendation pipeline

`hard constraints → graph retrieval → scoring → evidence check → scenario creation → QA critic → narrative`

The LLM may explain a recommendation; it may not create unsupported salary, admission, vacancy or credential facts.

## Evaluation system

### Golden dataset
Maintain consented/anonymized representative cases for:
- 18–24 first career;
- 25–35 career change;
- 35–50 transition;
- low-information user;
- contradictory answers;
- strict constraints;
- Ukrainian/English language variants.

### Critical evals
- schema validity: 100% after retries;
- hard-constraint adherence: 100%;
- fabricated market facts: 0;
- key claim evidence grounding: target ≥98%;
- three scenarios are materially distinct;
- human-rated actionability and usefulness meet release threshold;
- prohibited diagnosis/guarantee language: 0.

## Model release process

1. Change prompt/model in registry.
2. Run offline eval suite.
3. Compare with production baseline.
4. Human review critical cases.
5. Canary to small traffic percentage.
6. Monitor quality/cost/latency.
7. Promote or rollback.

## Mentor tool permissions

Mentor may request tools such as:
- `get_active_roadmap`
- `list_user_tasks`
- `search_verified_opportunities`
- `create_draft_task`
- `request_guide_booking`
- `propose_replan`

Writes that materially alter a roadmap require user confirmation or Guide confirmation according to policy.

## Data rules

- Do not send unnecessary PII to models.
- Never log secrets or raw sensitive fields in generic tracing.
- Store prompt/model version on generated artifacts.
- A user can see which conclusions are hypotheses vs validated/verified facts.
