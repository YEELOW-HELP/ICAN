"""Structured domain errors for the Stage 1 services. Callers (Telegram
adapter, tests, a future API layer) catch these instead of parsing
message strings -- each carries a stable `code` a client/adapter can map
to a user-facing message or an HTTP status, per
docs/architecture/03_API_AND_EVENTS.md's error-model principle."""

from __future__ import annotations


class DomainError(Exception):
    code: str = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConsentRequiredError(DomainError):
    code = "consent_required"


class ProductAccessRequiredError(DomainError):
    code = "product_access_required"


class PromoCodeInvalidError(DomainError):
    code = "promo_code_invalid"


class PromoAllocationExhaustedError(DomainError):
    code = "promo_allocation_exhausted"


class InvalidStateTransitionError(DomainError):
    code = "invalid_state_transition"


class AssessmentNotFoundError(DomainError):
    code = "assessment_not_found"


class AssessmentOwnershipError(DomainError):
    """Raised when a caller tries to act on an InterviewSession that does
    not belong to them -- see the RBAC/security tests."""

    code = "assessment_ownership_error"


class InsufficientRoleError(DomainError):
    code = "insufficient_role"


class CVFileTooLargeError(DomainError):
    code = "cv_file_too_large"


class ConsentOwnershipError(DomainError):
    """Raised when withdraw_consent is called without an actor authorized
    to withdraw the target consent -- neither the owning user nor a
    sufficiently privileged admin."""

    code = "consent_ownership_error"


class ProfileGenerationInProgressError(DomainError):
    """Raised when generate_potential_profile is called for a user who
    already has a profile-generation attempt in status=GENERATING --
    prevents two concurrent calls from racing to create uncontrolled
    duplicate versions (Stage 2 brief §10/§12)."""

    code = "profile_generation_in_progress"


class NoCurrentProfileError(DomainError):
    code = "no_current_profile"


class UnfinishedAssessmentExistsError(DomainError):
    """A user may have at most one unfinished (draft/active/paused)
    InterviewSession at a time (Founder decision, Issue #1 readiness
    review item 3) -- DB-enforced via a partial unique index, this is the
    friendly application-level surface of that same rule. The caller
    should resume the existing session, not start a new one."""

    code = "unfinished_assessment_exists"


# ---- Stage 3A: Career Knowledge Base (Issue #4) ----


class NoCurrentKnowledgeBaseVersionError(DomainError):
    """No published KnowledgeBaseVersion exists yet -- retrieval callers
    get this instead of silently reading nothing or reading a DRAFT."""

    code = "no_current_knowledge_base_version"


class KnowledgeBaseVersionNotFoundError(DomainError):
    code = "knowledge_base_version_not_found"


class KnowledgeBaseVersionNotDraftError(DomainError):
    """Careers/skills/relations/facts may only be added to a DRAFT
    version -- a PUBLISHED version is immutable (brief §14)."""

    code = "knowledge_base_version_not_draft"


class CareerNotFoundError(DomainError):
    code = "career_not_found"


class DuplicateCareerCodeError(DomainError):
    """Raised when a career `code` is added twice within the same
    (still-DRAFT) KnowledgeBaseVersion -- `code` is the stable business
    key and must be unique within a version."""

    code = "duplicate_career_code"


class CrossVersionRelationError(DomainError):
    """A CareerRelation must connect two careers in the same
    KnowledgeBaseVersion -- a relation spanning two different KB versions
    is never a meaningful thing to create."""

    code = "cross_version_relation"


class MarketSensitiveFactRequiresSourceError(DomainError):
    """Brief §20: a market-sensitive fact (salary, demand, growth, ...)
    without a source must never be persisted -- "unknown" beats a
    plausible-looking fabrication."""

    code = "market_sensitive_fact_requires_source"


class HardFactualRequirementRequiresSourceError(DomainError):
    """Brief §9: a CareerRequirement marked HARD_FACTUAL (as opposed to
    TYPICAL_RECOMMENDATION or UNKNOWN) must carry a source -- otherwise it
    is not actually a verified fact."""

    code = "hard_factual_requirement_requires_source"


# ---- MNP V1 (MNP_DEVELOPMENT_PACKAGE_V1) -- Career KB / Career Card ----
# `Mnp`-prefixed to distinguish unambiguously from the Stage 3A errors
# above, which belong to a different, superseded career-vector schema.


class MnpCareerNotFoundError(DomainError):
    code = "mnp_career_not_found"


class MnpDuplicateCareerCodeError(DomainError):
    """`MnpCareer.code` is the stable MNP_CAREER_ID business key -- unique
    across the whole catalog, not just within one version (unlike Stage
    3A's per-KB-version uniqueness)."""

    code = "mnp_duplicate_career_code"


class MnpInvalidLifecycleTransitionError(DomainError):
    """MNP_CAREER_KB_ARCHITECTURE_V1 "Lifecycle": DRAFT -> VALIDATED ->
    ACTIVE -> REVIEW_DUE -> ACTIVE/ARCHIVED (+ restore ARCHIVED ->
    ACTIVE). Any other transition is rejected outright, not silently
    coerced."""

    code = "mnp_invalid_lifecycle_transition"


class MnpSkillNotFoundError(DomainError):
    code = "mnp_skill_not_found"


class MnpCareerCardNotFoundError(DomainError):
    code = "mnp_career_card_not_found"
