"""Release decision data models.

This module contains Pydantic models for representing release decisions,
policy evaluations, notifications, and audit records from the Release
Decision Agent.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from src.models.perf_report import PerformanceAnalysisReport
from src.models.risk_assessment import RiskAssessment
from src.models.test_report import TestAnalysisReport


class NotificationRecord(BaseModel):
    """Tracks a notification that was sent as part of a release decision.

    Records the channel, recipient, message type, and delivery status
    for auditing and debugging purposes.
    """

    model_config = ConfigDict(frozen=True)

    channel: Literal["slack", "pagerduty", "email", "github_status"]
    recipient: str = Field(
        description="e.g., '#releases', 'oncall-eng', 'alice@company.com'"
    )
    message_type: Literal["approval", "block", "review_request", "override"]
    sent_at: datetime
    success: bool
    error: str | None = None


class PolicyEvaluation(BaseModel):
    """Records which policy was applied and how the decision was reached.

    Contains all the threshold values, flags, and override information
    needed to understand why a particular decision was made.
    """

    model_config = ConfigDict(frozen=True)

    environment: str = Field(description="e.g., 'production', 'staging'")
    policy_version: str = "1.0"
    risk_threshold_approve: int = Field(description="The threshold that was used for approval")
    risk_threshold_review: int = Field(description="The threshold above which review is required")
    actual_risk_score: int
    deployment_window_ok: bool
    freeze_period_ok: bool
    overrides_applied: list[str] = Field(
        default_factory=list, description="Override reasons like 'Critical service affected'"
    )
    raw_decision: Literal["APPROVE", "BLOCK", "REQUEST_REVIEW"] = Field(
        description="What the thresholds said"
    )
    final_decision: Literal["APPROVE", "BLOCK", "REQUEST_REVIEW"] = Field(
        description="After overrides were applied"
    )

    @computed_field
    @property
    def was_overridden(self) -> bool:
        """Return True if the final decision differs from the raw decision."""
        return self.raw_decision != self.final_decision

    def to_summary(self) -> str:
        """Generate a human-readable summary of the policy evaluation.

        Returns:
            A summary string like "Policy (production v1.0): score 33 vs thresholds [approve≤25, review≤50] → REQUEST_REVIEW. 1 override applied."
        """
        override_str = ""
        if self.overrides_applied:
            override_str = f" {len(self.overrides_applied)} override applied."

        return (
            f"Policy ({self.environment} v{self.policy_version}): "
            f"score {self.actual_risk_score} vs thresholds "
            f"[approve\u226425, review\u2264{self.risk_threshold_review}] "
            f"\u2192 {self.final_decision}.{override_str}"
        )



    """Immutable, complete record of a release decision and all inputs that led to it.

    This is the compliance artifact — it must contain everything needed to fully
    reconstruct the decision process months or years later. Includes snapshots
    of all agent outputs and execution metrics.
    """

    model_config = ConfigDict(frozen=True)

    decision_id: str = Field(description="UUID for this audit record")
    build_id: str
    commit_sha: str
    environment: str
    decision: ReleaseDecision
    test_report_snapshot: TestAnalysisReport | None = None
    perf_report_snapshot: PerformanceAnalysisReport | None = None
    risk_assessment_snapshot: RiskAssessment | None = None
    graph_execution_time_seconds: float = Field(
        ge=0, description="Total LangGraph workflow execution time"
    )
    agent_timings: dict[str, float] = Field(
        default_factory=dict,
        description="Per-agent execution times: {'test_analyst': 12.3, 'performance': 8.7, ...}",
    )
    errors_encountered: list[str] = Field(default_factory=list)
    created_at: datetime

    @computed_field
    @property
    def had_errors(self) -> bool:
        """Return True if any errors were encountered during execution."""
        return len(self.errors_encountered) > 0

    @computed_field
    @property
    def is_complete(self) -> bool:
        """Return True if all three snapshots (test, perf, risk) are present."""
        return (
            self.test_report_snapshot is not None
            and self.perf_report_snapshot is not None
            and self.risk_assessment_snapshot is not None
        )

    def to_summary(self) -> str:
        """Generate a human-readable summary of the audit record.

        Returns:
            A summary string like "Audit [abc-123]: build-1847 → REQUEST_REVIEW (33/100) in 24.5s. Complete: yes, Errors: none"
        """
        short_id = self.decision_id[:7] if len(self.decision_id) >= 7 else self.decision_id
        complete_str = "yes" if self.is_complete else "no"
        errors_str = "none" if not self.had_errors else str(len(self.errors_encountered))

        return (
            f"Audit [{short_id}]: {self.build_id} \u2192 {self.decision.decision} "
            f"({self.decision.risk_score}/100) in {self.graph_execution_time_seconds:.1f}s. "
            f"Complete: {complete_str}, Errors: {errors_str}"
        )
