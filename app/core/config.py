from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SIMULATION_MODE: bool = True
    ENV: str = "local"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "sqlite:///./data/incubrix.db"

    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "incubrix"
    S3_SECRET_KEY: str = "incubrix_secret"
    S3_BUCKET: str = "incubrix-distribution"
    S3_PUBLIC_BASE_URL: str = "http://localhost:9000/incubrix-distribution"
    S3_USE_SSL: bool = False

    DISCOURSE_MOCK_BASE_URL: str = "http://localhost:9101"
    DEVTO_MOCK_BASE_URL: str = "http://localhost:9102"
    WEBHOOK_RECEIVER_BASE_URL: str = "http://localhost:9103"
    LEMMY_BASE_URL: str = "http://localhost:8536"
    GHOST_BASE_URL: str = "http://localhost:2368"

    LEMMY_USERNAME: str = ""
    LEMMY_PASSWORD: str = ""
    GHOST_ADMIN_API_KEY: str = ""
    DISCOURSE_API_KEY: str = ""
    DISCOURSE_API_USERNAME: str = ""
    DEVTO_API_KEY: str = ""
    WEBHOOK_SHARED_SECRET: str = "dev_only_shared_secret_change_me"

    JOB_WORKER_POLL_SECONDS: float = 0.5
    BACKGROUND_THRESHOLD_SECONDS: float = 2.0
    CERTIFICATION_CLEANUP_DEADLINE_SECONDS: int = 600

    AI_PROVIDER: str = "mock"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    HOST: str = "0.0.0.0"
    PORT: int = 8080


settings = Settings()
