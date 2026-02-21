"""Risk assessment data models.

This module contains Pydantic models for representing risk breakdowns,
blast radius analysis, historical context, and complete risk assessments
from the Risk Scoring Agent.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class RiskBreakdown(BaseModel):
    """One component of the composite risk score, showing its individual contribution.

    Each risk category contributes to the overall risk score based on its
    raw score and assigned weight in the composite model.
    """

    model_config = ConfigDict(frozen=True)

    category: Literal[
        "test_risk",
        "performance_risk",
        "blast_radius_risk",
        "historical_risk",
        "change_velocity_risk",
    ]
    raw_score: float = Field(
        ge=0, le=100, description="Unweighted risk score for this category 0-100"
    )
    weight: float = Field(ge=0, le=1.0, description="Weight in the composite model")
    weighted_score: float = Field(ge=0, description="raw_score * weight")
    details: str = Field(
        description="Human-readable explanation, e.g., '2 new test failures detected, coverage dropped 3%'"
    )

    @model_validator(mode="after")
    def validate_weighted_score(self) -> "RiskBreakdown":
        """Ensure weighted_score equals raw_score * weight within floating point tolerance."""
        expected = self.raw_score * self.weight
        if abs(self.weighted_score - expected) > 0.01:
            raise ValueError(
                f"weighted_score ({self.weighted_score}) must equal "
                f"raw_score * weight ({self.raw_score} * {self.weight} = {expected})"
            )
        return self

    def to_summary(self) -> str:
        """Generate a human-readable summary of the risk breakdown.

        Returns:
            A summary string like "test_risk: 28.0 × 0.30 = 8.40 — 2 new test failures detected"
        """
        return (
            f"{self.category}: {self.raw_score:.1f} \u00d7 {self.weight:.2f} = "
            f"{self.weighted_score:.2f} \u2014 {self.details}"
        )


class BlastRadius(BaseModel):
    """Measures how far the impact of this change could spread across the system.

    Analyzes the scope of changes including affected services, critical paths,
    and downstream dependencies to estimate potential impact.
    """

    model_config = ConfigDict(frozen=True)

    files_changed: int = Field(ge=0)
    services_affected: list[str] = Field(default_factory=list)
    critical_services_affected: list[str] = Field(
        default_factory=list, description="Services with criticality > 70"
    )
    downstream_dependencies: list[str] = Field(
        default_factory=list, description="Services that depend on the affected services"
    )
    estimated_users_affected: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_critical_services_in_affected(self) -> "BlastRadius":
        """Ensure every critical service is also in services_affected."""
        for critical in self.critical_services_affected:
            if critical not in self.services_affected:
                raise ValueError(
                    f"Critical service '{critical}' must also be in services_affected"
                )
        return self

    @computed_field
    @property
    def total_impact_zone(self) -> list[str]:
        """Return the unique union of services_affected and downstream_dependencies."""
        return list(set(self.services_affected) | set(self.downstream_dependencies))

    @computed_field
    @property
    def involves_critical_path(self) -> bool:
        """Return True if any critical services are affected."""
        return len(self.critical_services_affected) > 0

    @computed_field
    @property
    def scope(self) -> Literal["minimal", "moderate", "large", "extreme"]:
        """Determine the scope of the blast radius.

        Returns:
            - minimal: 0-1 services, 0 critical
            - moderate: 2-3 services, 0-1 critical
            - large: 4-6 services OR 2+ critical
            - extreme: 7+ services OR 3+ critical
        """
        num_services = len(self.services_affected)
        num_critical = len(self.critical_services_affected)

        # Check extreme first (7+ services OR 3+ critical)
        if num_services >= 7 or num_critical >= 3:
            return "extreme"
        # Check large (4-6 services OR 2+ critical)
        if num_services >= 4 or num_critical >= 2:
            return "large"
        # Check moderate (2-3 services, 0-1 critical)
        if num_services >= 2:
            return "moderate"
        # minimal (0-1 services, 0 critical)
        return "minimal"

    def to_summary(self) -> str:
        """Generate a human-readable summary of the blast radius.

        Returns:
            A summary string like "Blast radius: 3 services (1 critical: payment-service), 5 downstream"
        """
        num_services = len(self.services_affected)
        num_critical = len(self.critical_services_affected)
        num_downstream = len(self.downstream_dependencies)

        critical_str = ""
        if num_critical > 0:
            critical_names = ", ".join(self.critical_services_affected)
            critical_str = f" ({num_critical} critical: {critical_names})"

        return (
            f"Blast radius: {num_services} services{critical_str}, "
            f"{num_downstream} downstream"
        )


class HistoricalContext(BaseModel):
    """Deployment history signals for risk assessment.

    Provides historical data about a service's deployment track record
    including rollback rates, incidents, and recovery times.
    """

    model_config = ConfigDict(frozen=True)

    service: str
    total_deployments_analyzed: int = Field(ge=0)
    rollback_count: int = Field(ge=0)
    rollback_rate: float = Field(ge=0.0, le=1.0)
    incident_count: int = Field(ge=0)
    avg_recovery_time_minutes: float | None = Field(default=None, ge=0)
    similar_change_outcomes: list[str] = Field(
        default_factory=list,
        description="Outcomes of historically similar changes: 'success', 'rollback', 'incident'",
    )
    last_rollback_days_ago: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_rollback_count(self) -> "HistoricalContext":
        """Ensure rollback_count does not exceed total_deployments_analyzed."""
        if self.rollback_count > self.total_deployments_analyzed:
            raise ValueError(
                f"rollback_count ({self.rollback_count}) cannot exceed "
                f"total_deployments_analyzed ({self.total_deployments_analyzed})"
            )
        return self

    @computed_field
    @property
    def is_high_risk_service(self) -> bool:
        """Return True if more than 15% of deploys get rolled back."""
        return self.rollback_rate > 0.15

    def to_summary(self) -> str:
        """Generate a human-readable summary of the historical context.

        Returns:
            A summary string like "checkout-service: 2 rollbacks in last 20 deploys (10%), last rollback 12 days ago"
        """
        rollback_pct = self.rollback_rate * 100
        last_rollback_str = ""
        if self.last_rollback_days_ago is not None:
            last_rollback_str = f", last rollback {self.last_rollback_days_ago} days ago"

        return (
            f"{self.service}: {self.rollback_count} rollbacks in last "
            f"{self.total_deployments_analyzed} deploys ({rollback_pct:.0f}%){last_rollback_str}"
        )


class RiskAssessment(BaseModel):
    """Complete output of the Risk Scoring Agent. The central decision-making data structure.

    Aggregates all risk signals into a composite score with detailed breakdown,
    blast radius analysis, and actionable recommendations.
    """

    model_config = ConfigDict(frozen=True)

    build_id: str
    composite_risk_score: int = Field(
        ge=0, le=100, description="0 = no risk, 100 = maximum risk. LOWER is safer."
    )
    confidence_level: Literal["HIGH", "MEDIUM", "LOW", "CRITICAL"]
    risk_breakdown: list[RiskBreakdown] = Field(
        description="Individual risk components that sum to the composite score"
    )
    blast_radius: BlastRadius
    historical_context: HistoricalContext | None = None
    narrative: str = Field(description="LLM-generated 2-4 sentence risk explanation")
    recommended_actions: list[str] = Field(
        default_factory=list, description="Specific actions to reduce risk"
    )
    timestamp: datetime

    @model_validator(mode="after")
    def validate_weighted_scores_sum(self) -> "RiskAssessment":
        """Ensure sum of weighted_scores approximately equals composite_risk_score."""
        total_weighted = sum(rb.weighted_score for rb in self.risk_breakdown)
        if abs(total_weighted - self.composite_risk_score) > 1.0:
            raise ValueError(
                f"Sum of weighted_scores ({total_weighted:.2f}) must approximately equal "
                f"composite_risk_score ({self.composite_risk_score}) within 1.0 tolerance"
            )
        return self

    @model_validator(mode="after")
    def validate_confidence_level_matches_score(self) -> "RiskAssessment":
        """Ensure confidence_level matches the score thresholds.

        - 0-20: HIGH (safe)
        - 21-50: MEDIUM
        - 51-75: LOW
        - 76-100: CRITICAL
        """
        score = self.composite_risk_score
        expected_level: Literal["HIGH", "MEDIUM", "LOW", "CRITICAL"]

        if score <= 20:
            expected_level = "HIGH"
        elif score <= 50:
            expected_level = "MEDIUM"
        elif score <= 75:
            expected_level = "LOW"
        else:
            expected_level = "CRITICAL"

        if self.confidence_level != expected_level:
            raise ValueError(
                f"confidence_level '{self.confidence_level}' does not match "
                f"expected '{expected_level}' for score {score}"
            )
        return self

    @computed_field
    @property
    def is_auto_approvable(self) -> bool:
        """Return True if the risk is low enough for automatic approval."""
        return self.confidence_level == "HIGH"

    @computed_field
    @property
    def requires_block(self) -> bool:
        """Return True if the risk is critical and should block deployment."""
        return self.confidence_level == "CRITICAL"

    @computed_field
    @property
    def top_risk_factor(self) -> RiskBreakdown | None:
        """Return the RiskBreakdown with the highest weighted_score."""
        if not self.risk_breakdown:
            return None
        return max(self.risk_breakdown, key=lambda rb: rb.weighted_score)

    def to_summary(self) -> str:
        """Generate a human-readable summary of the risk assessment.

        Returns:
            A summary string like "Risk Assessment: score 33/100 (MEDIUM) — top factor: performance_risk (13.5). Recommend: investigate P99 latency regression."
        """
        top_factor = self.top_risk_factor
        top_factor_str = ""
        if top_factor:
            top_factor_str = (
                f" \u2014 top factor: {top_factor.category} ({top_factor.weighted_score:.1f})"
            )

        recommend_str = ""
        if self.recommended_actions:
            recommend_str = f". Recommend: {self.recommended_actions[0]}"

        return (
            f"Risk Assessment: score {self.composite_risk_score}/100 "
            f"({self.confidence_level}){top_factor_str}{recommend_str}"
        )
