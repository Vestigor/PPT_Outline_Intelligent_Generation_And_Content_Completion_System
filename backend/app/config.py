from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "PPT Intelligent Generation System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/ppt_system"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TASK_DB: int = 1
    REDIS_CACHE_TTL: int = 3600  # seconds

    # Auth / JWT
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OSS
    OSS_ENDPOINT: str = "http://localhost:9000"
    OSS_ACCESS_KEY: str = "minioadmin"
    OSS_SECRET_KEY: str = "minioadmin"
    OSS_BUCKET_NAME: str = "ppt-files"
    OSS_REGION: str = "us-east-1"

    # LLM
    LLM_PROVIDER: str = "openai"          
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL_NAME: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096
    LLM_STREAM_TIMEOUT: int = 120

    # ── Embedding ─────────────────────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIMENSION: int = 1024

    # ── pgvector
    PGVECTOR_URL: str = ""

    # ── RAG ───────────────────────────────────────────────────────────────────
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.75
    RAG_TIMEOUT_SECONDS: int = 5

    # DeepSearch
    SEARCH_PROVIDER: str = "tavily"
    SEARCH_API_KEY: str = ""
    SEARCH_MAX_RESULTS: int = 10
    SEARCH_TIMEOUT_SECONDS: int = 15

    # Task Worker
    TASK_CHUNK_TTL: int = 3600           # SSE chunk TTL in Redis (seconds)
    TASK_MAX_RETRIES: int = 3
    TASK_RETRY_DELAY: int = 5

    # ── File Processing ───────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "md", "txt"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()