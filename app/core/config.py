from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    anthropic_api_key: str = ""
    database_url: str = "postgresql+asyncpg://ican:ican@localhost:5432/ican"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # Guardrails against runaway Claude API spend if the agent never reaches
    # ready_for_confirmation (e.g. a confused loop of clarifying questions).
    max_screening_turns: int = 20
    history_window: int = 20

    # Rapid-fire messages (e.g. a candidate splitting one answer across two
    # Telegram messages) are batched into a single API call instead of one
    # call per message.
    debounce_seconds: float = 1.5


settings = Settings()
