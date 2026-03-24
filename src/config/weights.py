"""Risk weight models and YAML loader.

Usage:
    from src.config.weights import get_risk_weights, get_confidence_thresholds

    weights = get_risk_weights()
    level  = get_confidence_thresholds().get_level(score=34)  # "MEDIUM"
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskWeightDistribution(BaseModel):
    """Weights for the composite risk scoring formula. Must sum to 1.0.

    Each weight represents the fraction of the composite score contributed
    by that risk category. If the weights do not sum to 1.0, the composite
    score will land on a different scale than the policy thresholds expect.
    """

    model_config = ConfigDict(frozen=True)

    test_risk: float = Field(ge=0.0, le=1.0)
    performance_risk: float = Field(ge=0.0, le=1.0)
    blast_radius_risk: float = Field(ge=0.0, le=1.0)
    historical_risk: float = Field(ge=0.0, le=1.0)
    change_velocity_risk: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "RiskWeightDistribution":
        """Ensure all weights sum to approximately 1.0 (±0.001 tolerance)."""
        total = (
            self.test_risk
            + self.performance_risk
            + self.blast_radius_risk
            + self.historical_risk
            + self.change_velocity_risk
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Risk weights must sum to 1.0, but got {total:.6f}. "
                "Adjust the weights in risk_weights.yaml so they total exactly 1.0."
            )
        return self

    def as_dict(self) -> dict[str, float]:
        """Return the weights as a plain dict for easy iteration.

        Example:
            {"test_risk": 0.30, "performance_risk": 0.30, ...}
        """
        return {
            "test_risk": self.test_risk,
            "performance_risk": self.performance_risk,
            "blast_radius_risk": self.blast_radius_risk,
            "historical_risk": self.historical_risk,
            "change_velocity_risk": self.change_velocity_risk,
        }


class ConfidenceThresholds(BaseModel):
    """Maps risk score ranges to human-readable confidence levels.

    Thresholds are upper bounds (inclusive) for each level:
        0 – HIGH:     safe to deploy
        HIGH+1 – MEDIUM: needs attention
        MEDIUM+1 – LOW:  risky
        LOW+1 – CRITICAL: do not deploy
    """

    model_config = ConfigDict(frozen=True)

    HIGH: int = Field(ge=0, le=100, description="Scores 0 to this value = HIGH confidence")
    MEDIUM: int = Field(ge=0, le=100)
    LOW: int = Field(ge=0, le=100)
    CRITICAL: int = Field(le=100)

    @model_validator(mode="after")
    def thresholds_ascending(self) -> "ConfidenceThresholds":
        """Ensure thresholds are strictly ascending: HIGH < MEDIUM < LOW < CRITICAL."""
        if not (self.HIGH < self.MEDIUM < self.LOW < self.CRITICAL):
            raise ValueError(
                f"Confidence thresholds must be strictly ascending. "
                f"Got HIGH={self.HIGH}, MEDIUM={self.MEDIUM}, LOW={self.LOW}, CRITICAL={self.CRITICAL}"
            )
        return self

    def get_level(self, score: int) -> str:
        """Map a composite risk score to its confidence level string.

        Args:
            score: Integer risk score in 0–100 range.

        Returns:
            One of "HIGH", "MEDIUM", "LOW", or "CRITICAL".
        """
        if score <= self.HIGH:
            return "HIGH"
        if score <= self.MEDIUM:
            return "MEDIUM"
        if score <= self.LOW:
            return "LOW"
        return "CRITICAL"


class ScoringPenalties(BaseModel):
    """Configurable penalties applied by agents when computing confidence scores.

    Each agent starts at 100 and subtracts penalties for bad signals, then
    optionally adds bonuses for good ones. The resulting value is the agent's
    confidence score, which feeds into the composite risk calculation.
    """

    model_config = ConfigDict(frozen=True)

    # Test Analyst penalties (subtracted from 100)
    new_bug_penalty: int = Field(ge=0, default=15)
    coverage_drop_penalty_per_pct: int = Field(ge=0, default=2)
    flaky_blocking_penalty: int = Field(ge=0, default=5)
    no_failures_bonus: int = Field(ge=0, default=5)

    # Performance Agent penalties (subtracted from 100)
    regression_penalty: int = Field(ge=0, default=20)
    slo_violation_penalty: int = Field(ge=0, default=25)
    anomaly_penalty: int = Field(ge=0, default=10)
    missing_data_penalty: int = Field(ge=0, default=5)

    # Risk Scoring Agent adjustments
    critical_service_penalty: int = Field(ge=0, default=15)
    high_rollback_rate_penalty: int = Field(ge=0, default=10)
    large_changeset_penalty: int = Field(ge=0, default=10)


class RiskWeightsConfig(BaseModel):
    """Top-level risk weights configuration."""

    weights: RiskWeightDistribution
    confidence_thresholds: ConfidenceThresholds
    scoring: ScoringPenalties


def load_risk_weights(config_path: str | None = None) -> RiskWeightsConfig:
    """Load risk weights from a YAML file.

    Args:
        config_path: Path to the YAML file. Defaults to
                     src/config/risk_weights.yaml (relative to this module).

    Returns:
        Validated RiskWeightsConfig.

    Raises:
        FileNotFoundError: if the config file does not exist.
        pydantic.ValidationError: if the YAML contents do not match the schema.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "risk_weights.yaml"

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Risk weights config not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    return RiskWeightsConfig.model_validate(raw)


def get_risk_weights(config_path: str | None = None) -> RiskWeightDistribution:
    """Convenience function to get just the weight distribution."""
    return load_risk_weights(config_path).weights


def get_confidence_thresholds(config_path: str | None = None) -> ConfidenceThresholds:
    """Convenience function to get just the confidence thresholds."""
    return load_risk_weights(config_path).confidence_thresholds


def get_scoring_penalties(config_path: str | None = None) -> ScoringPenalties:
    """Convenience function to get just the scoring penalties."""
    return load_risk_weights(config_path).scoring
