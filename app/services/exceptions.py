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
