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


class NoEligibleAssessmentSessionError(DomainError):
    """Raised by the Stage 4A.5 admin-fallback profile-generation entry
    point (app/services/profile/generation.py::generate_profile_for_user)
    when the user has no InterviewSession in COMPLETE/PROCESSING/READY --
    there is nothing `generate_potential_profile` could legally act on
    yet (Stage 1's own minimum-data rule was never satisfied)."""

    code = "no_eligible_assessment_session"


class ProfileAlreadyExistsError(DomainError):
    """Raised by the same admin-fallback entry point when the user
    already has a current READY `PotentialProfile` -- the fallback is a
    pilot-reliability safety net for a missing/failed automatic
    generation, not a general "regenerate" button (Founder Stage 4A.5
    §3: "only if it does not already exist")."""

    code = "profile_already_exists"


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


# ---- Stage 3B: Direction Intelligence (Founder decisions A-M) ----


class NoActiveScoringConfigError(DomainError):
    """No ACTIVE ScoringConfig exists -- Direction Intelligence cannot run
    without versioned (experimental) weights/thresholds. Call
    app/services/direction/config.py::ensure_experimental_scoring_config."""

    code = "no_active_scoring_config"


class NoActiveRankingPolicyError(DomainError):
    """No ACTIVE RankingPolicy exists -- ranking is a separate versioned
    decision layer (Founder decisions O + G). Call
    app/services/direction/config.py::ensure_experimental_ranking_policy."""

    code = "no_active_ranking_policy"


class DirectionGenerationInProgressError(DomainError):
    """A DirectionRun is already GENERATING for this user -- prevents two
    concurrent runs racing to create uncontrolled duplicate versions (the
    Stage 2 ProfileGenerationInProgressError precedent). Reserved for the
    Slice 2 orchestrator."""

    code = "direction_generation_in_progress"


class NoCurrentDirectionRunError(DomainError):
    """No `DirectionRun` exists at all for this user -- there is nothing
    for the Critic/review/approval layer to act on yet. Call
    app/services/direction/pipeline.py::generate_directions first."""

    code = "no_current_direction_run"


class DirectionReviewNotFoundError(DomainError):
    """No `DirectionReview` row exists for this `DirectionRun` -- call
    app/services/direction/review.py::start_review first."""

    code = "direction_review_not_found"


class DirectionRunHasUnresolvedBlockerError(DomainError):
    """A `DirectionRun` with at least one unresolved
    `DirectionCriticFinding(severity=BLOCKER)` may never be
    consultant-approved (Founder decision, Slice 3 §3/§7)."""

    code = "direction_run_has_unresolved_blocker"


class NoApprovedDirectionRunError(DomainError):
    """No `DirectionRun` for this user has cleared the full approval gate
    (READY status, zero unresolved BLOCKER findings, an APPROVED
    `DirectionReview` from an authorized reviewer, bound to the exact
    immutable run version) -- a later client-report layer must never treat
    an unapproved run as final."""

    code = "no_approved_direction_run"


# ---- Matching V1 M1: BASIC structured assessment (Founder Review, 2026-08-28) ----


class BasicAssessmentDefinitionNotFoundError(DomainError):
    """No active `AssessmentDefinition` exists for the requested mode --
    call `app/services/basic_assessment/seed.py::seed_alpha_long_form`
    first."""

    code = "basic_assessment_definition_not_found"


class BasicAttemptClosedError(DomainError):
    """A `BasicAssessmentAttempt` in COMPLETED or CALCULATED state can
    never receive a new answer -- "completed attempt cannot be silently
    edited" (Founder Review, M1 test #18)."""

    code = "basic_attempt_closed"


class InvalidResponseError(DomainError):
    """A structured answer's payload does not match its `AssessmentItem`'s
    `response_type`/option set."""

    code = "invalid_response"


# ---- Matching V1 M2: deterministic BASIC profile (Founder Review, 2026-08-28) ----


class BasicAttemptNotCompletedError(DomainError):
    """`calculate_basic_profile` requires a `BasicAssessmentAttempt` in
    COMPLETED (or already CALCULATED, for idempotent re-entry) status --
    an IN_PROGRESS/NOT_STARTED attempt has no profile to compute."""

    code = "basic_attempt_not_completed"


class NoCurrentBasicProfileError(DomainError):
    """No `DeterministicProfile` with `is_current=True` exists for this
    user -- call `calculate_basic_profile` first."""

    code = "no_current_basic_profile"


# ---- Matching V1 M3: Career Vector Knowledge Base (Founder Review, 2026-08-28) ----


class CareerAlreadyMappedError(DomainError):
    """A `CareerExternalMapping(career_id, source_system, external_code)`
    already exists -- re-import is idempotent, not additive; callers
    should check first rather than relying on this to no-op silently."""

    code = "career_already_mapped"


class NoCurrentCareerMatchingProfileError(DomainError):
    """No `CareerMatchingProfile` with `is_current=True` exists for this
    career -- call `create_career_matching_profile` (or the Alpha seed)
    first."""

    code = "no_current_career_matching_profile"


class MatchDisabledScaleError(DomainError):
    """Attempted to create a `CareerMatchingComponent` for a scale whose
    MNP mapping_status is PROXY or MNP_ONLY (matching_usage=PROFILE_ONLY)
    -- the hard Founder Review §8/§9 invariant: PROFILE_ONLY is never a
    career-side matching vector, no exceptions, no silent override."""

    code = "match_disabled_scale"


# ---- Matching V1 M4: deterministic matching engine (Founder Review, 2026-08-28) ----


class MatchingResultNotFoundError(DomainError):
    """No `MatchingResult` exists for the requested id -- call
    `app/services/matching/engine.py::calculate_pair_match` or
    `match_profile_to_careers` first."""

    code = "matching_result_not_found"
