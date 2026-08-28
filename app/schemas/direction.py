"""Request bodies for the Stage 4A MNP consultant workspace API
(app/api/direction.py). Response payloads are the existing Stage 3B/3.5
read-model dataclasses (app/services/direction/readmodel.py) returned
as-is -- FastAPI's default JSON encoding already handles dataclasses/
UUID/datetime/Enum, so no parallel response-schema layer is authored here
(thin handlers, single source of truth stays the service layer)."""

from __future__ import annotations

from pydantic import BaseModel


class GenerateDirectionsRequest(BaseModel):
    knowledge_base_version_id: str | None = None


class CreateCorrectionRequest(BaseModel):
    artifact_type: str  # "direction_placement" | "narrative" | "profile_flag" | "knowledge_flag"
    reason_code: str  # one of the 13 approved CorrectionReasonCode values
    comment: str | None = None
    direction_id: str | None = None
    corrected_placement: str | None = None  # required for artifact_type == "direction_placement"
    corrected_text: str | None = None  # required for artifact_type in ("narrative",)
    narrative_field: str = "summary"


class ReviewDecisionRequest(BaseModel):
    comment: str | None = None


class ReviewDecisionWithReasonRequest(BaseModel):
    comment: str
