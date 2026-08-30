"""Lightweight, YAML-authored research schema for the Human Lab, validated
against the approved MNP enums (imported verbatim from the model modules —
see findings/MISSING_APPROVED_DOCS_FINDING_V1.md for why the code is the
effective schema).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.db.models_career_card import ProficiencyLevel, EvidenceType, WorkFormat, CareerGoalType
from app.db.models_career_kb_mnp import RequirementCategory
from app.db.models_matching_mnp import (
    FeasibilityStatus, TransitionDistance, GapType, GapClassification, GapAction, FindingStatus,
)

# enum value sets (str) for validation
PROFICIENCY = {e.value for e in ProficiencyLevel}                     # basic / working / strong
EVIDENCE = {e.value for e in EvidenceType}                           # claimed / inferred / verified
FEASIBILITY = {e.value for e in FeasibilityStatus}                   # ready_now / near_ready / reachable / long_transition / blocked
TRANSITION = {e.value for e in TransitionDistance}                  # d0_same_career ... d5_fundamental_retraining
GAP_TYPE = {e.value for e in GapType}
GAP_CLASS = {e.value for e in GapClassification}
GAP_ACTION = {e.value for e in GapAction}
FINDING = {e.value for e in FindingStatus}                          # pass / gap / blocker
REQ_CATEGORY = {e.value for e in RequirementCategory}
WORK_FORMAT = {e.value for e in WorkFormat}
GOAL_TYPE = {e.value for e in CareerGoalType}
MATCH_STATE = {"match", "partial_gap", "full_gap", "unknown"}       # MNP_SKILL_GAP_AND_PRIORITY_V1


class ValidationError(Exception):
    pass


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def _in(value: str, allowed: set[str], where: str) -> None:
    _require(value in allowed, f"{where}: '{value}' not in {sorted(allowed)}")


# --------------------------------------------------------------------------
# Person Profile  (brief §15)
# --------------------------------------------------------------------------
@dataclass
class PersonSkill:
    name: str
    proficiency: str          # PROFICIENCY
    evidence: str             # EVIDENCE  (UNKNOWN is represented by simply omitting the skill)
    note: str = ""


@dataclass
class PersonProfile:
    persona_id: str
    label: str
    segment: str              # experienced_professional / unemployed / career_changer / idp / veteran / return_to_ukraine / incomplete_cv / no_cv / legal_blocker / high_fit_low_confidence / transferable_skills
    last_role: str
    years_experience: float | None
    responsibilities: list[str] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    credentials: list[str] = field(default_factory=list)
    languages: list[dict] = field(default_factory=list)          # [{language, level}]
    skills: list[PersonSkill] = field(default_factory=list)
    knowledge: list[PersonSkill] = field(default_factory=list)
    preferences: dict = field(default_factory=dict)              # {work_format, work_objects: [...], environment: [...]}
    values_ranked: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)              # GOAL_TYPE values
    constraints: list[dict] = field(default_factory=list)       # [{category, description, hardness, severity}]
    learning_hours_per_week: float | None = None
    learning_budget_uah: float | None = None
    reviewer: str = ""
    note: str = ""

    def validate(self) -> None:
        _require(self.persona_id and " " not in self.persona_id, "persona_id must be a slug")
        for s in list(self.skills) + list(self.knowledge):
            _in(s.proficiency, PROFICIENCY, f"skill '{s.name}' proficiency")
            _in(s.evidence, EVIDENCE, f"skill '{s.name}' evidence")
        for g in self.goals:
            _in(g, GOAL_TYPE, "goal")
        if self.preferences.get("work_format"):
            _in(self.preferences["work_format"], WORK_FORMAT, "preferences.work_format")
        for c in self.constraints:
            _require("category" in c and "hardness" in c, "constraint needs category + hardness")
            _in(c["category"], REQ_CATEGORY, "constraint.category")
            _in(c["hardness"], {"soft", "hard"}, "constraint.hardness")


# --------------------------------------------------------------------------
# Human Career Comparison  (brief §16)
# --------------------------------------------------------------------------
@dataclass
class ComparisonLine:
    component: str            # skill_fit / experience_transfer / knowledge_fit / preference_fit / values_fit / feasibility / transition_cost / confidence
    person_value: str
    career_requirement: str
    source: str               # ESCO / ONET / MNP_EDITORIAL / MNP_CALCULATION / HUMAN_JUDGEMENT / UNKNOWN
    match_state: str          # MATCH_STATE
    human_decision: str
    comment: str = ""

    _COMPONENTS = {"skill_fit", "experience_transfer", "knowledge_fit", "preference_fit",
                   "values_fit", "feasibility", "transition_cost", "confidence"}
    _SOURCES = {"ESCO", "ONET", "ISCO", "CROSSWALK", "MNP_EDITORIAL", "MNP_CALCULATION",
                "HUMAN_JUDGEMENT", "UNKNOWN"}

    def validate(self) -> None:
        _in(self.component, self._COMPONENTS, "comparison.component")
        _in(self.source, self._SOURCES, "comparison.source")
        _in(self.match_state, MATCH_STATE, "comparison.match_state")


@dataclass
class CareerComparison:
    persona_id: str
    career_code: str          # MNP career code
    lines: list[ComparisonLine] = field(default_factory=list)
    reviewer: str = ""

    def validate(self) -> None:
        for line in self.lines:
            line.validate()


# --------------------------------------------------------------------------
# Human Expected Result  (brief §18)
# --------------------------------------------------------------------------
@dataclass
class ExpectedGap:
    skill_or_knowledge: str
    gap_type: str            # GAP_TYPE
    classification: str      # GAP_CLASS
    action: str              # GAP_ACTION

    def validate(self) -> None:
        _in(self.gap_type, GAP_TYPE, "expected gap.gap_type")
        _in(self.classification, GAP_CLASS, "expected gap.classification")
        _in(self.action, GAP_ACTION, "expected gap.action")


@dataclass
class ExpectedResult:
    persona_id: str
    expected_top_careers: list[str]
    acceptable_careers: list[str]
    unacceptable_careers: list[str]
    expected_feasibility: dict            # {career_code: FEASIBILITY band}
    expected_transition_distance: dict   # {career_code: TRANSITION}
    expected_gaps: list[ExpectedGap] = field(default_factory=list)
    expected_unknowns: list[str] = field(default_factory=list)
    expected_blockers: list[str] = field(default_factory=list)
    rationale: str = ""
    reviewer: str = ""
    methodology_version: str = "mnp_v1"
    career_kb_version: str = "seed_alpha_v1"

    def validate(self) -> None:
        for c, band in self.expected_feasibility.items():
            _in(band, FEASIBILITY, f"expected_feasibility[{c}]")
        for c, d in self.expected_transition_distance.items():
            _in(d, TRANSITION, f"expected_transition_distance[{c}]")
        for g in self.expected_gaps:
            g.validate()
        _require(not (set(self.expected_top_careers) & set(self.unacceptable_careers)),
                 "a career cannot be both expected-top and unacceptable")


# --------------------------------------------------------------------------
# YAML loading
# --------------------------------------------------------------------------
def _load_yaml(path: Path) -> dict:
    import yaml  # noqa: PLC0415

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_person(path: Path) -> PersonProfile:
    d = _load_yaml(path)
    d["skills"] = [PersonSkill(**s) for s in d.get("skills", [])]
    d["knowledge"] = [PersonSkill(**s) for s in d.get("knowledge", [])]
    p = PersonProfile(**d)
    p.validate()
    return p


def load_comparison(path: Path) -> CareerComparison:
    d = _load_yaml(path)
    d["lines"] = [ComparisonLine(**line) for line in d.get("lines", [])]
    c = CareerComparison(**d)
    c.validate()
    return c


def load_expected(path: Path) -> ExpectedResult:
    d = _load_yaml(path)
    d["expected_gaps"] = [ExpectedGap(**g) for g in d.get("expected_gaps", [])]
    e = ExpectedResult(**d)
    e.validate()
    return e
