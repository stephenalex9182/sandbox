from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://patchverify:patchverify@localhost:5432/patchverify"
    jwt_secret: str = Field(min_length=32)
    jwt_expire_minutes: int = 60
    frontend_origin: str = "http://localhost:8000"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    e2b_api_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    oauth_redirect_uri: str = "http://localhost:8000/api/auth/oauth/google/callback"
    max_patch_attempts: int = 3
    sandbox_timeout_seconds: int = 120
    max_output_bytes: int = 200_000
    max_project_file_bytes: int = 1_000_000
    max_project_total_bytes: int = 10_000_000

@lru_cache
def get_settings() -> Settings:
    return Settings()
