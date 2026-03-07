from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    ENVIRONMENT: str = "development"
    APP_NAME: str = "Speaking App"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://speaking_app:localdev@localhost:5432/speaking_app"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI — LLM providers (all optional; first available is used)
    OPENAI_API_KEY: str = ""
    GROK_API_KEY: str = ""        # xAI Grok
    GROQ_API_KEY: str = ""        # Groq (fast inference)
    GEMINI_API_KEY: str = ""      # Google Gemini
    DEEPSEEK_API_KEY: str = ""    # DeepSeek
    ANTHROPIC_API_KEY: str = ""

    # Provider priority order (comma-separated). First available key wins.
    # e.g. "openai,grok,gemini,deepseek"
    LLM_PROVIDER_ORDER: str = "openai,groq,grok,gemini,deepseek"

    # TTS provider priority: "elevenlabs,openai"
    TTS_PROVIDER_ORDER: str = "elevenlabs,openai"
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" default

    # Media
    DEEPGRAM_API_KEY: str = ""

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Session limits
    MAX_SPEAKERS_PER_ROOM: int = 5
    MAX_SESSION_DURATION_SEC: int = 3600  # 1 hour

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
