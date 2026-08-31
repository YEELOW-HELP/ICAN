"""Career Route construction (`MNP_ROUTE_ENGINE_V1`): TODAY -> existing
capital -> reframe/prove -> learn/practice/certify -> first evidence ->
entry opportunity -> target role -> next step. Built directly from the
already-computed `PersonalGapResult`s -- never generated via LLM."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.matching_mnp.gap import ACTION_LEARN, ACTION_PRACTICE, ACTION_REFRAME, PersonalGapResult

STEP_EXISTING_CAPITAL = "existing_capital"
STEP_REFRAME_OR_PROVE = "reframe_or_prove"
STEP_LEARN_PRACTICE_CERTIFY = "learn_practice_certify"
STEP_FIRST_EVIDENCE = "first_evidence"
STEP_ENTRY_OPPORTUNITY = "entry_opportunity"
STEP_TARGET_ROLE = "target_role"
STEP_NEXT_STEP = "next_step"


@dataclass(frozen=True)
class RouteStepResult:
    order: int
    step_type: str
    title: str
    description: str | None = None
    target_skill_key: str | None = None


def build_route_steps(
    *, career_label: str, matched_skill_labels: list[str], gaps: list[PersonalGapResult],
) -> list[RouteStepResult]:
    steps: list[RouteStepResult] = []
    order = 1

    if matched_skill_labels:
        steps.append(
            RouteStepResult(
                order=order, step_type=STEP_EXISTING_CAPITAL, title="Використайте наявний досвід",
                description="Вже підтверджено: " + ", ".join(matched_skill_labels[:5]),
            )
        )
        order += 1

    reframe_gaps = [g for g in gaps if g.action == ACTION_REFRAME]
    if reframe_gaps:
        steps.append(
            RouteStepResult(
                order=order, step_type=STEP_REFRAME_OR_PROVE, title="Переформулюйте свій досвід",
                description="Покажіть " + ", ".join(g.reference_label for g in reframe_gaps[:3]),
            )
        )
        order += 1

    learn_practice_gaps = [g for g in gaps if g.action in (ACTION_LEARN, ACTION_PRACTICE)]
    for gap_item in learn_practice_gaps[:5]:  # MNP_SKILL_GAP_AND_PRIORITY_V1 "UX": top 3-5, not an exhaustive list
        verb = "Вивчіть" if gap_item.action == ACTION_LEARN else "Попрактикуйте"
        steps.append(
            RouteStepResult(
                order=order, step_type=STEP_LEARN_PRACTICE_CERTIFY, title=f"{verb}: {gap_item.reference_label}",
                target_skill_key=gap_item.reference_key,
            )
        )
        order += 1

    if learn_practice_gaps or reframe_gaps:
        steps.append(
            RouteStepResult(
                order=order, step_type=STEP_FIRST_EVIDENCE, title="Отримайте перше підтвердження",
                description="Невеликий проєкт, тестове завдання або відгук, що підтверджує новий рівень",
            )
        )
        order += 1

    steps.append(
        RouteStepResult(
            order=order, step_type=STEP_ENTRY_OPPORTUNITY, title="Знайдіть точку входу",
            description=f"Розгляньте вакансії або стажування за напрямом «{career_label}»",
        )
    )
    order += 1

    steps.append(RouteStepResult(order=order, step_type=STEP_TARGET_ROLE, title=career_label))
    order += 1

    steps.append(
        RouteStepResult(
            order=order, step_type=STEP_NEXT_STEP, title="Плануйте наступний крок кар'єри",
            description="Після входу в професію -- перегляньте кар'єрну карту знову",
        )
    )
    return steps
