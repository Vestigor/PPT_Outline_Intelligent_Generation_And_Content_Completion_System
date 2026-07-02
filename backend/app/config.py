from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # 本地开发默认读取可提交的 .env.dev；私有 .env（若存在）具有更高优先级。
        env_file=(".env.dev", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "PPT Intelligent Generation System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["https://ppt.vestigor.top"]

    # ── Database ──────────────────────────────────────────────────────────────
    # POSTGRES_* initializes the Compose container; DATABASE_URL is used by the app.
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "ppt_system"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@postgres:5432/ppt_system"
    # Worker 持有 DB session 跨整个任务执行（>= LLM stream 时长），需要更大的池：
    # 8 个并发 worker 任务 + 多路 SSE 订阅 + 普通 API 请求 + 周期任务恢复
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    DATABASE_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_PASSWORD: str = "123456"
    REDIS_URL: str = "redis://:123456@redis:6379/0"
    REDIS_ENCODING: str = "utf-8"
    REDIS_DECODE_RESPONSES: bool = True
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_HEALTH_CHECK_INTERVAL: int = 30

    # ── Auth / JWT ────────────────────────────────────────────────────────────
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 3
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── MinIO / S3 ────────────────────────────────────────────────────────────
    # MINIO_ROOT_* initializes the container; OSS_* is used by the app.
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    OSS_ENDPOINT: str = "http://minio:9000"
    OSS_ACCESS_KEY: str = "minioadmin"
    OSS_SECRET_KEY: str = "minioadmin"
    OSS_BUCKET_NAME: str = "ppt-files"
    OSS_REGION: str = "us-east-1"
    OSS_MAX_POOL_CONNECTIONS: int = 50
    OSS_MAX_ATTEMPTS: int = 3

    # ── LLM ───────────────────────────────────────────────────────────────────
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096
    LLM_STREAM_TIMEOUT: int = 120

    # ── Embedding ─────────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "text-embedding-v4"
    EMBEDDING_DIMENSION: int = 1024
    DASHSCOPE_API_KEY: str = ""

    # ── RAG ───────────────────────────────────────────────────────────────────
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.7

    # ── Web Search ────────────────────────────────────────────────────────────
    SEARCH_MAX_RESULTS: int = 10

    # ── File Processing ───────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "md", "txt"]

    # ── Email / SMTP ──────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.yeah.net"
    SMTP_PORT: int = 465
    SMTP_USE_SSL: bool = True
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM_NAME: str = "PPT 智能生成系统"
    EMAIL_CODE_TTL_SECONDS: int = 600   # 10 minutes

    # ── Password Policy ───────────────────────────────────────────────────────
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_MAX_LENGTH: int = 16

    # ── Middleware ────────────────────────────────────────────────────────────
    SLOW_REQUEST_THRESHOLD_MS: int = 2000  # log warning for requests exceeding this
    GZIP_MINIMUM_SIZE: int = 1024

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_not_be_default(cls, v: str) -> str:
        if v == "change-me-in-production-use-openssl-rand-hex-32":
            import warnings
            warnings.warn(
                "SECRET_KEY is set to the default placeholder. "
                "Set a strong random value via: openssl rand -hex 32",
                stacklevel=2,
            )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
