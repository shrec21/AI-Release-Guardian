"""Application settings and configuration."""

import functools

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables and .env file.

    All env vars are prefixed with GUARDIAN_ to avoid collisions.
    Example: GUARDIAN_ANTHROPIC_API_KEY=sk-ant-...

    Load order (later sources win):
        1. Default values defined below
        2. .env file (if present)
        3. Actual environment variables
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GUARDIAN_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Don't crash on unexpected env vars
    )

    # --- LLM Configuration ---
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude",
    )
    llm_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model to use for LLM-powered classification and narrative generation",
    )
    llm_max_tokens: int = Field(default=4096, ge=1)
    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="0.0 for deterministic classification, higher for narrative generation",
    )

    # --- Database ---
    database_url: str = Field(
        default="postgresql://guardian:guardian@localhost:5432/guardian",
        description="PostgreSQL connection string for audit logs and state checkpoints",
    )

    # --- CI/CD Integration ---
    jenkins_url: str = Field(default="", description="Jenkins base URL")
    jenkins_token: str = Field(default="", description="Jenkins API token")
    github_token: str = Field(
        default="", description="GitHub personal access token for commit statuses"
    )
    github_repo: str = Field(default="", description="GitHub repo in owner/repo format")

    # --- MCP Server Commands ---
    mcp_jenkins_command: str = "node"
    mcp_jenkins_args: list[str] = Field(
        default_factory=lambda: ["./mcp-servers/jenkins/dist/index.js"]
    )
    mcp_test_logs_command: str = "node"
    mcp_test_logs_args: list[str] = Field(
        default_factory=lambda: ["./mcp-servers/test-logs/dist/index.js"]
    )
    mcp_perf_baselines_command: str = "python"
    mcp_perf_baselines_args: list[str] = Field(
        default_factory=lambda: ["./mcp-servers/perf-baselines/server.py"]
    )
    mcp_deploy_history_command: str = "python"
    mcp_deploy_history_args: list[str] = Field(
        default_factory=lambda: ["./mcp-servers/deploy-history/server.py"]
    )

    # --- Notifications ---
    slack_webhook_url: str = Field(default="", description="Slack incoming webhook URL")
    slack_channel: str = Field(default="#releases")
    pagerduty_api_key: str = Field(
        default="", description="PagerDuty API key for escalations"
    )
    pagerduty_service_id: str = Field(default="")

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = False

    # --- Feature Flags ---
    enable_slack_notifications: bool = Field(
        default=False,
        description="Set True when Slack webhook is configured",
    )
    enable_pagerduty_alerts: bool = Field(
        default=False,
        description="Set True when PagerDuty is configured",
    )
    enable_github_statuses: bool = Field(
        default=False,
        description="Set True when GitHub token is configured",
    )
    dry_run: bool = Field(
        default=True,
        description=(
            "When True, decisions are logged but pipeline is NOT actually triggered. "
            "Safe for testing."
        ),
    )


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns cached Settings instance.

    Call this everywhere instead of constructing Settings() directly.
    The instance is created once and reused for the lifetime of the process.
    To reload settings in tests, call get_settings.cache_clear() first.
    """
    return Settings()
