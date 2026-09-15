from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.core.paths import BACKEND_ROOT, DATA_ROOT


class Settings(BaseSettings):
    # hide_input_in_errors: a rejected value (e.g. a malformed
    # ANTHROPIC_API_KEY / JWT secret / DB URL) must never be echoed back
    # in the ValidationError text or logs.
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore", hide_input_in_errors=True)

    telegram_bot_token: str = ""
    anthropic_api_key: str = ""
    cv_analysis_model: str = "claude-sonnet-5"
    cv_analysis_enabled: bool = False
    cv_analysis_daily_limit: int = Field(default=5, ge=1, le=100)
    # MongoDB is the only database used by the web runtime.
    mongodb_url: SecretStr = SecretStr("")
    mongodb_database: str = "ican"
    # Read only by the archived SQL modules/tests during rollback validation.
    # The production entry point never imports those modules.
    database_url: str = f"sqlite+aiosqlite:///{(DATA_ROOT / 'dev' / 'mnp_dev.sqlite').as_posix()}"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # Guardrails against runaway Claude API spend if the agent never reaches
    # ready_for_confirmation (e.g. a confused loop of clarifying questions).
    max_screening_turns: int = 20
    history_window: int = 20

    # Rapid-fire messages (e.g. a candidate splitting one answer across two
    # Telegram messages) are batched into a single API call instead of one
    # call per message.
    debounce_seconds: float = 1.5

    # Admin dashboard auth
    jwt_secret: str = ""
    jwt_expire_minutes: int = 60 * 12

    # CRM client files — local disk by default (see app/services/crm/storage.py
    # for why, and its known limitation on ephemeral hosting filesystems).
    file_storage_dir: str = str(DATA_ROOT / "client_files")
    max_upload_size_mb: int = 15

    # Private Dropbox storage for staff-attached CV files. Credentials are
    # server-only; the browser never receives them or a shared file link.
    dropbox_root: str = ""
    dropbox_app_key: SecretStr = SecretStr("")
    dropbox_app_secret: SecretStr = SecretStr("")
    dropbox_refresh_token: SecretStr = SecretStr("")

    # Stage 1 (МОЖУ: Мій Напрям V1) -- whole-bot-mode switch. "legacy" keeps
    # today's ICAN 1.1 Telegram screening exactly as-is (default, so nothing
    # changes unless explicitly switched); "v1" registers the new Hybrid
    # assessment handlers instead. Never both at once in one process, to
    # avoid ambiguous double /start routing (docs/product/15_..._ROADMAP.md
    # Stage 1: "Introduce the new V1 flow behind a feature flag").
    bot_flow: str = "legacy"
    default_locale: str = "uk"

    # Safety valve mirroring legacy max_screening_turns -- caps total
    # adaptive questions per Stage 1 assessment session even under repeated
    # contradictions, so the interview can never run forever.
    max_assessment_questions: int = 20

    # Stage 2 (Evidence + Human Potential Profile). An Answer idempotency
    # reservation (extracted_value IS NULL) older than this is considered
    # abandoned -- e.g. the process that created it crashed before either
    # finishing extraction or cleaning up on failure -- and is safe to
    # discard: the raw text survives independently in InterviewMessage, so
    # nothing is lost. Never treated as evidence before this timeout.
    pending_answer_stale_after_seconds: int = 300

    # MNP V1 (MNP_DEVELOPMENT_PACKAGE_V1) -- resume storage. Reuses the
    # same `max_upload_size_mb` limit as CRM client files (MNP_SECURITY_
    # PRIVACY_V1 "Controls": file type/size validation). Local disk today,
    # same known ephemeral-hosting caveat as app/services/crm/storage.py;
    # `storage_ref` is an opaque path, never raw bytes in the DB.
    mnp_resume_storage_dir: str = str(DATA_ROOT / "mnp_resumes")

    # Official labour-market snapshots. The startup worker first performs a
    # cheap CKAN metadata check and downloads the large XML only when its
    # resource id changed. Disable explicitly in constrained deployments.
    market_data_auto_refresh: bool = True
    market_data_refresh_hours: int = 24

    @field_validator("anthropic_api_key")
    @classmethod
    def _validate_anthropic_api_key(cls, value: str) -> str:
        """Reject a malformed secret before the first provider request.

        Anthropic sends the API key as an HTTP header, so it must be ASCII
        with no surrounding whitespace. Without this, a pasted non-ASCII or
        whitespace-padded value fails much later inside httpx with a
        misleading UnicodeEncodeError / header error. An empty key stays
        allowed (existing behaviour -- the default). The secret value is
        never included in the exception message or logs.
        """
        if not value:
            return value
        if value != value.strip():
            raise ValueError("ANTHROPIC_API_KEY must not contain leading or trailing whitespace")
        if not value.isascii():
            raise ValueError("ANTHROPIC_API_KEY must contain ASCII characters only")
        return value

    @field_validator("cv_analysis_model")
    @classmethod
    def _validate_cv_analysis_model(cls, value: str) -> str:
        if value not in {"claude-sonnet-5", "claude-haiku-4-5-20251001"}:
            raise ValueError("CV_ANALYSIS_MODEL is not in the allowed model list")
        return value


settings = Settings()
