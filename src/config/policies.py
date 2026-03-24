"""Release policy models and YAML loader.

Usage:
    from src.config.policies import get_policy

    policy = get_policy("production")
    allowed, reason = policy.can_deploy_now()
"""

from datetime import date, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FreezePeriod(BaseModel):
    """A date range during which deployments are blocked."""

    model_config = ConfigDict(frozen=True)

    start: date
    end: date
    reason: str

    @model_validator(mode="after")
    def start_before_end(self) -> "FreezePeriod":
        """Ensure the freeze period start is not after its end date."""
        if self.start > self.end:
            raise ValueError(
                f"Freeze period start ({self.start}) must be <= end ({self.end})"
            )
        return self


class DeploymentWindow(BaseModel):
    """Rules about when deployments are allowed."""

    model_config = ConfigDict(frozen=True)

    blocked_hours: list[int] = Field(
        default_factory=list,
        description="Hours (0-23) when deploys are blocked",
    )
    blocked_days: list[int] = Field(
        default_factory=list,
        description="ISO weekday numbers (1=Mon … 7=Sun) when deploys are blocked",
    )

    @field_validator("blocked_hours")
    @classmethod
    def hours_in_range(cls, v: list[int]) -> list[int]:
        """Ensure every hour value is in 0-23."""
        bad = [h for h in v if not (0 <= h <= 23)]
        if bad:
            raise ValueError(f"blocked_hours values must be 0-23, got: {bad}")
        return v

    @field_validator("blocked_days")
    @classmethod
    def days_in_range(cls, v: list[int]) -> list[int]:
        """Ensure every day value is in 1-7 (ISO weekday)."""
        bad = [d for d in v if not (1 <= d <= 7)]
        if bad:
            raise ValueError(f"blocked_days values must be 1-7 (ISO weekday), got: {bad}")
        return v

    def is_allowed_now(self) -> bool:
        """Return True if a deployment is permitted at the current moment.

        Checks the current wall-clock hour and ISO weekday against the
        blocked lists. Both must be clear for deployment to be allowed.
        """
        now = datetime.now()
        if now.hour in self.blocked_hours:
            return False
        if now.isoweekday() in self.blocked_days:
            return False
        return True

    def next_allowed_window(self) -> str:
        """Return a human-readable description of the next deployment window.

        Scans forward hour-by-hour (up to 7 days) to find the next slot
        that is not blocked by hour or by day.

        Returns:
            "Deployments allowed now" if currently unblocked, otherwise
            a string like "Next deployment window: Monday 06:00 AM".
        """
        if self.is_allowed_now():
            return "Deployments allowed now"

        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
                     5: "Friday", 6: "Saturday", 7: "Sunday"}

        from datetime import timedelta
        for offset in range(1, 7 * 24 + 1):
            candidate = now + timedelta(hours=offset)
            if candidate.hour not in self.blocked_hours and candidate.isoweekday() not in self.blocked_days:
                day_name = day_names[candidate.isoweekday()]
                time_str = candidate.strftime("%I:%M %p").lstrip("0")
                return f"Next deployment window: {day_name} {time_str}"

        return "No deployment window found in the next 7 days"


class ReleasePolicy(BaseModel):
    """Release policy for a specific environment."""

    model_config = ConfigDict(frozen=True)

    risk_threshold_approve: int = Field(ge=0, le=100)
    risk_threshold_review: int = Field(ge=0, le=100)
    require_human_approval: bool = False
    min_test_confidence: int = Field(ge=0, le=100)
    min_perf_confidence: int = Field(ge=0, le=100)
    deployment_windows: DeploymentWindow = Field(default_factory=DeploymentWindow)
    freeze_periods: list[FreezePeriod] = Field(default_factory=list)
    max_files_changed_without_review: int = Field(ge=1, default=50)
    critical_services: list[str] = Field(default_factory=list)
    required_approvers: int = Field(ge=0, default=1)

    @model_validator(mode="after")
    def approve_threshold_below_review(self) -> "ReleasePolicy":
        """Ensure approve threshold is never higher than the review threshold.

        If approve > review, a risky build (score between the two values)
        would be auto-approved rather than sent for review — the opposite
        of the intended behaviour.
        """
        if self.risk_threshold_approve > self.risk_threshold_review:
            raise ValueError(
                f"risk_threshold_approve ({self.risk_threshold_approve}) must be "
                f"<= risk_threshold_review ({self.risk_threshold_review})"
            )
        return self

    def is_in_freeze(self) -> tuple[bool, str | None]:
        """Check whether today falls within any configured freeze period.

        Returns:
            (True, reason) if currently frozen, (False, None) otherwise.
        """
        today = date.today()
        for period in self.freeze_periods:
            if period.start <= today <= period.end:
                return True, period.reason
        return False, None

    def can_deploy_now(self) -> tuple[bool, str | None]:
        """Check whether a deployment is permitted right now.

        Evaluates deployment window rules first, then freeze periods.

        Returns:
            (True, None) if deployment is allowed.
            (False, reason) if blocked, with a human-readable explanation.
        """
        if not self.deployment_windows.is_allowed_now():
            next_window = self.deployment_windows.next_allowed_window()
            return False, f"Outside deployment window. {next_window}"

        frozen, freeze_reason = self.is_in_freeze()
        if frozen:
            return False, f"Deployment freeze in effect: {freeze_reason}"

        return True, None


class ReleasePoliciesConfig(BaseModel):
    """Top-level config containing all environment policies."""

    environments: dict[str, ReleasePolicy]


def load_policies(config_path: str | None = None) -> ReleasePoliciesConfig:
    """Load release policies from a YAML file.

    Args:
        config_path: Path to the YAML file. Defaults to
                     src/config/release_policies.yaml (relative to this module).

    Returns:
        Validated ReleasePoliciesConfig.

    Raises:
        FileNotFoundError: if the config file does not exist.
        pydantic.ValidationError: if the YAML contents do not match the schema.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "release_policies.yaml"

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Release policies config not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    return ReleasePoliciesConfig.model_validate(raw)


def get_policy(environment: str, config_path: str | None = None) -> ReleasePolicy:
    """Convenience function to get the policy for a specific environment.

    Args:
        environment: Environment name (e.g. "production", "staging").
        config_path: Optional path override passed through to load_policies.

    Returns:
        The ReleasePolicy for the requested environment.

    Raises:
        KeyError: if the environment is not present in the config.
        FileNotFoundError: if the config file does not exist.
        pydantic.ValidationError: if the config is malformed.
    """
    config = load_policies(config_path)
    if environment not in config.environments:
        available = list(config.environments.keys())
        raise KeyError(
            f"No policy for environment '{environment}'. Available: {available}"
        )
    return config.environments[environment]
