"""Typed process settings for the bootstrap runtime."""

import base64
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from open_commerce import __version__


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and `.env`."""

    app_name: str = "Open Commerce Agent"
    app_version: str = __version__
    environment: Literal["local_demo", "development", "test"] = "local_demo"
    auth_mode: Literal["local_demo"] = "local_demo"
    runtime_profile: Literal["legacy_demo", "self_hosted", "hosted"] = "self_hosted"
    public_origins: list[str] = Field(default_factory=list)
    public_hosts: list[str] = Field(default_factory=list)
    encryption_key: SecretStr | None = Field(default=None, repr=False)
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = Field(default=None, repr=False)
    oidc_callback_url: str | None = None
    hosted_daily_request_limit: int | None = Field(default=None, ge=1)
    hosted_daily_token_limit: int | None = Field(default=None, ge=1000)
    asset_directory: Path = Path(".opencommerce/assets")
    api_host: Literal["127.0.0.1", "0.0.0.0"] = "127.0.0.1"
    max_request_bytes: int = Field(default=65536, ge=1024, le=1048576)
    write_requests_per_minute: int = Field(default=120, ge=1, le=600)
    expensive_requests_per_minute: int = Field(default=30, ge=1, le=120)
    log_level: str = "INFO"
    deployment_kill_switch: bool = False
    database_url: str = "postgresql+asyncpg://opencommerce:opencommerce@localhost:5432/opencommerce"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    search_embedding_backend: Literal["hash", "minilm"] = "hash"
    search_model_directory: Path | None = None
    manager_periodic_memory_turns: int = Field(default=6, ge=2, le=50)
    manager_model_provider: Literal["deterministic", "openai"] = "deterministic"
    manager_model_id: str = "gpt-5.4-mini"
    manager_model_timeout_seconds: float = Field(default=45, ge=1, le=90)
    manager_model_max_iterations: int = Field(default=12, ge=1, le=30)
    manager_model_max_tool_calls: int = Field(default=10, ge=0, le=30)
    manager_model_max_output_tokens: int = Field(default=2048, ge=128, le=8192)
    manager_model_max_input_bytes: int = Field(default=64000, ge=4000, le=256000)
    manager_run_active_seconds: int = Field(default=300, ge=30, le=900)
    local_runtime_id: UUID | None = None
    local_runtime_manifest: Path | None = None
    local_operations_enabled: bool = False
    manager_web_health_url: str = "http://127.0.0.1:3000/health"
    shopper_web_health_url: str = "http://127.0.0.1:3001/health"
    shopper_session_days: int = Field(default=7, ge=1, le=30)
    manager_dataset_request_bytes: int = Field(default=1_048_576, ge=65_536, le=1_048_576)
    openai_api_key: SecretStr | None = Field(default=None, repr=False)
    shopify_catalog_enabled: bool = False
    shopify_shop_domain: str | None = None
    shopify_admin_access_token: SecretStr | None = Field(default=None, repr=False)
    openai_api_base_url: str = "https://api.openai.com/v1"
    readiness_timeout_seconds: float = Field(default=2.0, gt=0.0, le=30.0)
    request_id_header: str = "x-request-id"
    local_tenant_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    simulator_state_dir: str = ".opencommerce/simulator"
    model_enabled: bool = False
    model_local_only_attested: bool = False
    model_url: str = "http://127.0.0.1:11434"
    model_id: str = "qwen3:4b"
    model_digest: str = ""
    model_timeout_seconds: float = Field(default=60, ge=1, le=90)
    model_max_iterations: int = Field(default=4, ge=1, le=6)
    model_max_tool_calls: int = Field(default=3, ge=0, le=5)
    model_max_output_tokens: int = Field(default=1024, ge=128, le=2048)
    model_max_input_bytes: int = Field(default=16000, ge=2000, le=24000)
    model_goal_request_limit: int = Field(default=40, ge=1, le=100)
    model_goal_token_limit: int = Field(default=720000, ge=1000, le=1800000)
    model_daily_request_limit: int = Field(default=150, ge=1, le=500)
    model_daily_token_limit: int = Field(default=2700000, ge=1000, le=9000000)
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3010",
            "http://127.0.0.1:3010",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OPEN_COMMERCE_",
        extra="ignore",
    )

    @field_validator("openai_api_key")
    @classmethod
    def empty_openai_credential_is_missing(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_runtime_profile(self) -> "Settings":
        if self.runtime_profile == "hosted":
            if not all(
                (
                    self.oidc_issuer,
                    self.oidc_client_id,
                    self.oidc_client_secret,
                    self.oidc_callback_url,
                    self.encryption_key,
                    self.hosted_daily_request_limit,
                    self.hosted_daily_token_limit,
                )
            ):
                raise ValueError("Hosted mode requires OIDC, encryption, and deployment budgets")
            if self.local_operations_enabled:
                raise ValueError("Local process recovery is not available in hosted mode")
            if not self.public_origins or any(
                urlsplit(origin).scheme != "https" for origin in self.public_origins
            ):
                raise ValueError("Hosted mode requires explicit HTTPS public origins")
            if not self.public_hosts:
                raise ValueError("Hosted mode requires explicit public hosts")
            callback = urlsplit(self.oidc_callback_url or "")
            if (
                callback.scheme != "https"
                or f"{callback.scheme}://{callback.netloc}" not in self.public_origins
                or callback.hostname not in self.public_hosts
                or callback.username
                or callback.password
                or callback.query
                or callback.fragment
            ):
                raise ValueError("Hosted OIDC callback must use an exact configured HTTPS origin")
            if not self.oidc_client_secret or not self.oidc_client_secret.get_secret_value():
                raise ValueError("Hosted mode requires a nonempty OIDC client secret")
        if self.encryption_key and self.encryption_key.get_secret_value():
            try:
                decoded = base64.urlsafe_b64decode(self.encryption_key.get_secret_value())
            except ValueError as exc:
                raise ValueError("Instance encryption key must be base64 encoded") from exc
            if len(decoded) != 32:
                raise ValueError("Instance encryption key must contain 32 random bytes")
        elif self.runtime_profile == "hosted":
            raise ValueError("Hosted mode requires a nonempty encryption key")
        for origin in self.public_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Public origins must be exact configured origins")
        if any("*" in host or "/" in host or ":" in host for host in self.public_hosts):
            raise ValueError("Public hosts must be exact hostnames, never wildcards")
        return self

    @property
    def worker_queue(self) -> str:
        suffix = f":{self.local_runtime_id}" if self.local_runtime_id else ""
        if self.runtime_profile != "legacy_demo":
            return f"arq:stores{suffix}"
        return f"arq:queue:{self.local_tenant_id}{suffix}"

    @property
    def worker_job_timeout_seconds(self) -> float:
        if not self.model_enabled:
            return max(90, self.manager_run_active_seconds + 30)
        return max(
            self.manager_run_active_seconds + 30,
            self.model_max_iterations * (self.model_timeout_seconds + 5) + 30,
        )

    @field_validator("model_url")
    @classmethod
    def validate_model_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("the model service must be an exact loopback HTTP origin")
        _ = parsed.port
        return value.rstrip("/")

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, value: str) -> str:
        if (
            not value
            or len(value) > 100
            or "cloud" in value.lower()
            or not all(c.isalnum() or c in ":._-/" for c in value)
        ):
            raise ValueError("a bounded local model identifier is required")
        return value

    @field_validator("manager_model_id")
    @classmethod
    def validate_manager_model_id(cls, value: str) -> str:
        if not value or len(value) > 100 or not all(c.isalnum() or c in "._-/" for c in value):
            raise ValueError("a bounded manager model identifier is required")
        return value

    @field_validator("openai_api_base_url")
    @classmethod
    def validate_openai_api_base_url(cls, value: str) -> str:
        if value.rstrip("/") != "https://api.openai.com/v1":
            raise ValueError("the OpenAI provider must use the official HTTPS API origin")
        return value.rstrip("/")

    @field_validator("manager_web_health_url", "shopper_web_health_url")
    @classmethod
    def validate_local_web_health_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "web", "shopper"}
            or parsed.username
            or parsed.password
            or parsed.path != "/health"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("web health probes must use an exact local /health URL")
        _ = parsed.port
        return value

    @field_validator("cors_allow_origins")
    @classmethod
    def validate_demo_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("local-demo CORS requires exact loopback origins")
            _ = parsed.port
        return origins


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for process entrypoints."""

    return Settings()
