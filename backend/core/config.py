"""
Application configuration loaded from environment variables.
No hardcoded secrets. All sensitive values must be provided via .env
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # Security
    secret_key: str  # Used for JWT signing AND as base for AES key derivation
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Argon2id parameters
    argon2_memory_cost: int = 65536
    argon2_time_cost: int = 3
    argon2_parallelism: int = 4

    # AI
    anthropic_api_key: str
    claude_model: str = "claude-3-5-sonnet-20241022"
    ai_max_tokens: int = 2048
    embedding_dimensions: int = 1536
    rag_top_k: int = 5

    # Email
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    email_from: str
    email_verify_expire_hours: int = 24
    password_reset_expire_hours: int = 1

    # App
    app_env: str = "development"
    app_url: str = "http://localhost"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    proficiency_threshold: float = 0.70
    small_group_suppression_threshold: int = 5
    max_csv_upload_rows: int = 5000
    max_csv_file_size_mb: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
