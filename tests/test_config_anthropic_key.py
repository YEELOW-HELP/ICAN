"""`Settings.anthropic_api_key` validation.

Ported from `stage-1-hotfix-anthropic-key-validation` (Repository Cleanup
V1). The key is sent as an HTTP header, so a non-ASCII / whitespace-padded
value must fail early with a clear config error instead of later inside
httpx with a misleading UnicodeEncodeError. The secret value must never
appear in the error.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_anthropic_api_key_empty_is_allowed():
    """Empty key stays allowed -- the existing default behaviour."""
    assert Settings(anthropic_api_key="").anthropic_api_key == ""


def test_anthropic_api_key_accepts_ascii_value():
    assert Settings(anthropic_api_key="sk-ant-test-123").anthropic_api_key == "sk-ant-test-123"


def test_anthropic_api_key_rejects_non_ascii_without_leaking_secret():
    secret = "sk-ant-тест-secret"
    with pytest.raises(ValidationError) as exc_info:
        Settings(anthropic_api_key=secret)
    message = str(exc_info.value)
    assert "ANTHROPIC_API_KEY must contain ASCII characters only" in message
    assert secret not in message
    assert "тест" not in message


def test_anthropic_api_key_rejects_surrounding_whitespace_without_leaking_secret():
    secret = "sk-ant-test-123"
    with pytest.raises(ValidationError) as exc_info:
        Settings(anthropic_api_key=f"  {secret}  ")
    message = str(exc_info.value)
    assert "must not contain leading or trailing whitespace" in message
    assert secret not in message


def test_other_settings_still_load_alongside_the_validator():
    """The validator is additive -- every current MNP / Stage 1 / Stage 2 /
    CRM setting still resolves to its default."""
    s = Settings(anthropic_api_key="sk-ant-ok")
    assert s.bot_flow == "legacy"
    assert s.max_assessment_questions == 20
    assert s.pending_answer_stale_after_seconds == 300
    assert s.mnp_resume_storage_dir == "./data/mnp_resumes"
    assert s.file_storage_dir == "./data/client_files"
    assert s.max_upload_size_mb == 15
