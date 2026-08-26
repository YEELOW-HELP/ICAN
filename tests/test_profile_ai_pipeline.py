"""Stage 2 brief §27 AI tests: every Stage 2 AI task goes through
AIGateway (never a direct provider call), structured output is validated,
malformed output is rejected safely, and provider failures propagate
rather than being swallowed. Mirrors tests/test_ai_gateway.py's fake
Anthropic client pattern so these tests exercise the real AIGateway, not
just a duck-typed fake extractor.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai_gateway import AIGateway
from app.db.models_profile import ClaimStatus, Evidence, EvidenceSourceType
from app.services.profile.claim_synthesis import ClaimSynthesizer, compute_claim_confidence
from app.services.profile.evidence_extraction import EvidenceExtractor
from app.services.profile.summary import ProfileSummarizer


def _client(tool_input: dict | None, stop_reason="tool_use"):
    block = None if tool_input is None else SimpleNamespace(type="tool_use", input=tool_input)
    response = SimpleNamespace(content=[] if block is None else [block], stop_reason=stop_reason, usage=None)
    return SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)))


def _failing_client(exc: Exception):
    return SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=exc)))


def _evidence(confidence=0.8):
    return Evidence(
        user_id="00000000-0000-0000-0000-000000000000", session_id="00000000-0000-0000-0000-000000000000",
        source_type=EvidenceSourceType.OPEN_ANSWER, source_id="00000000-0000-0000-0000-000000000000",
        evidence_type="test", normalized_text="observation", confidence=confidence, extraction_method="llm_extraction",
    )


# ---- Evidence Extractor ----

async def test_evidence_extractor_uses_ai_gateway_and_parses_valid_items():
    gateway = AIGateway(client=_client({"evidence_items": [
        {"evidence_type": "enjoys_coordination", "normalized_text": "Enjoys organizing events", "confidence": 0.8},
    ]}))
    extractor = EvidenceExtractor(gateway=gateway)

    result = await extractor.extract(question_prompt="key_skills_or_interests", raw_answer_text="I love organizing events")

    assert len(result.items) == 1
    assert result.items[0].evidence_type == "enjoys_coordination"
    assert result.items[0].confidence == 0.8
    assert result.trace_id  # provenance retained


async def test_evidence_extractor_rejects_malformed_items_safely():
    gateway = AIGateway(client=_client({"evidence_items": [
        {"evidence_type": "", "normalized_text": "missing type", "confidence": 0.8},  # empty evidence_type
        {"evidence_type": "ok", "normalized_text": "fine", "confidence": "not-a-number"},  # bad confidence
        {"evidence_type": "ok2", "normalized_text": "fine2", "confidence": 1.5},  # out of range
        {"normalized_text": "no evidence_type key at all", "confidence": 0.5},
    ]}))
    extractor = EvidenceExtractor(gateway=gateway)

    result = await extractor.extract(question_prompt="q", raw_answer_text="text")

    assert result.items == []  # every malformed item dropped, none crash the call


async def test_evidence_extractor_handles_completely_malformed_payload():
    gateway = AIGateway(client=_client({"unexpected_shape": True}))
    extractor = EvidenceExtractor(gateway=gateway)

    result = await extractor.extract(question_prompt="q", raw_answer_text="text")
    assert result.items == []


async def test_evidence_extractor_propagates_provider_failure():
    gateway = AIGateway(client=_failing_client(ConnectionError("provider down")))
    extractor = EvidenceExtractor(gateway=gateway)

    with pytest.raises(ConnectionError):
        await extractor.extract(question_prompt="q", raw_answer_text="text")


# ---- Claim Synthesizer ----

async def test_claim_synthesizer_uses_ai_gateway_and_parses_valid_claims():
    gateway = AIGateway(client=_client({"claims": [
        {
            "dimension": "strength", "term_key": "leadership_coordination", "label": "Лідерство",
            "normalized_value": "Схильність координувати", "evidence_indices": [0], "is_contradictory": False,
        }
    ]}))
    synthesizer = ClaimSynthesizer(gateway=gateway)

    result = await synthesizer.synthesize(evidence_items=[_evidence()], taxonomy_terms=[("leadership_coordination", "strength", "Лідерство")])

    assert len(result.proposals) == 1
    assert result.proposals[0].term_key == "leadership_coordination"
    assert result.trace_id


async def test_claim_synthesizer_rejects_malformed_claims_safely():
    gateway = AIGateway(client=_client({"claims": [
        {"dimension": "not_a_real_dimension", "label": "x", "normalized_value": "y", "evidence_indices": [0], "is_contradictory": False},
        {"dimension": "strength", "label": "", "normalized_value": "y", "evidence_indices": [0], "is_contradictory": False},
        {"dimension": "strength", "label": "x", "normalized_value": "y", "evidence_indices": "not-a-list", "is_contradictory": False},
    ]}))
    synthesizer = ClaimSynthesizer(gateway=gateway)

    result = await synthesizer.synthesize(evidence_items=[_evidence()], taxonomy_terms=[])
    assert result.proposals == []


async def test_claim_synthesizer_returns_empty_without_calling_gateway_when_no_evidence():
    gateway = AIGateway(client=_client({"claims": []}))
    synthesizer = ClaimSynthesizer(gateway=gateway)

    result = await synthesizer.synthesize(evidence_items=[], taxonomy_terms=[])

    assert result.proposals == []
    gateway._client.messages.create.assert_not_called()


async def test_claim_synthesizer_propagates_provider_failure():
    gateway = AIGateway(client=_failing_client(TimeoutError("timed out")))
    synthesizer = ClaimSynthesizer(gateway=gateway)

    with pytest.raises(TimeoutError):
        await synthesizer.synthesize(evidence_items=[_evidence()], taxonomy_terms=[])


# ---- Profile Summarizer ----

async def test_summarizer_uses_ai_gateway_and_parses_summary_text():
    gateway = AIGateway(client=_client({"summary_text": "Ти маєш сильні комунікативні навички."}))
    summarizer = ProfileSummarizer(gateway=gateway)

    from app.db.models_profile import ProfileClaim, ProfileDimension

    claim = ProfileClaim(
        profile_id="00000000-0000-0000-0000-000000000000", dimension=ProfileDimension.STRENGTH,
        label="Комунікація", normalized_value="...", confidence=0.7, status=ClaimStatus.SUPPORTED,
        generated_by="claim-synthesis-v1",
    )

    result = await summarizer.summarize(claims=[claim])
    assert "комунікативні" in result.summary_text
    assert result.trace_id


async def test_summarizer_handles_malformed_payload_safely():
    gateway = AIGateway(client=_client({"unexpected": True}))
    summarizer = ProfileSummarizer(gateway=gateway)

    from app.db.models_profile import ProfileClaim, ProfileDimension

    claim = ProfileClaim(
        profile_id="00000000-0000-0000-0000-000000000000", dimension=ProfileDimension.STRENGTH,
        label="X", normalized_value="...", confidence=0.7, status=ClaimStatus.SUPPORTED, generated_by="x",
    )
    result = await summarizer.summarize(claims=[claim])
    assert result.summary_text == ""


async def test_summarizer_propagates_provider_failure():
    gateway = AIGateway(client=_failing_client(RuntimeError("boom")))
    summarizer = ProfileSummarizer(gateway=gateway)

    from app.db.models_profile import ProfileClaim, ProfileDimension

    claim = ProfileClaim(
        profile_id="00000000-0000-0000-0000-000000000000", dimension=ProfileDimension.STRENGTH,
        label="X", normalized_value="...", confidence=0.7, status=ClaimStatus.SUPPORTED, generated_by="x",
    )
    with pytest.raises(RuntimeError):
        await summarizer.summarize(claims=[claim])
