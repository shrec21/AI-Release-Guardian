"""Performance report data models.

This module contains Pydantic models for representing benchmark results,
metric comparisons, SLO checks, and complete performance analysis outputs
from the Performance Agent.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


class BenchmarkResult(BaseModel):
    """Raw benchmark measurements for a service endpoint.

    Contains latency percentiles, throughput, memory usage, and error rates
    from a single benchmark run.
    """

    model_config = ConfigDict(frozen=True)

    service: str
    endpoint: str | None = Field(default=None, description="e.g., '/api/v1/checkout'")
    latency_p50_ms: float = Field(ge=0, description="Median latency in milliseconds")
    latency_p95_ms: float = Field(ge=0, description="95th percentile latency")
    latency_p99_ms: float = Field(ge=0, description="99th percentile latency")
    throughput_rps: float = Field(ge=0, description="Requests per second")
    memory_mb: float = Field(ge=0, description="Memory usage in megabytes")
    error_rate: float = Field(ge=0.0, le=1.0, description="Error rate as a fraction 0-1")
    sample_count: int = Field(ge=0, description="Number of requests in this benchmark run")

    @model_validator(mode="after")
    def validate_percentile_ordering(self) -> "BenchmarkResult":
        """Ensure latency percentiles are properly ordered: P50 <= P95 <= P99."""
        if not (self.latency_p50_ms <= self.latency_p95_ms <= self.latency_p99_ms):
            raise ValueError(
                f"Latency percentiles must be ordered: P50 ({self.latency_p50_ms}) <= "
                f"P95 ({self.latency_p95_ms}) <= P99 ({self.latency_p99_ms})"
            )
        return self

    def to_summary(self) -> str:
        """Generate a human-readable summary of the benchmark result.

        Returns:
            A summary string like "api-service /checkout: P50=45ms P99=218ms, 1250rps, 0.2% errors"
        """
        endpoint_str = f" {self.endpoint}" if self.endpoint else ""
        error_pct = self.error_rate * 100
        return (
            f"{self.service}{endpoint_str}: P50={self.latency_p50_ms:.0f}ms "
            f"P99={self.latency_p99_ms:.0f}ms, {self.throughput_rps:.0f}rps, "
            f"{error_pct:.1f}% errors"
        )


class MetricComparison(BaseModel):
    """Statistical comparison of a single metric against its historical baseline.

    Uses Welch's t-test for statistical significance and Cohen's d for
    practical significance to determine if a regression has occurred.
    """

    model_config = ConfigDict(frozen=True)

    metric_name: str = Field(description="e.g., 'latency_p99', 'throughput_rps', 'memory_mb'")
    service: str
    current_value: float
    baseline_mean: float
    baseline_stddev: float = Field(ge=0)
    baseline_sample_count: int = Field(ge=0)
    p_value: float = Field(ge=0.0, le=1.0, description="Welch's t-test p-value")
    cohens_d: float = Field(ge=0, description="Absolute effect size")
    is_regression: bool = Field(
        description="True only if BOTH p < 0.05 AND cohens_d > 0.5"
    )
    severity: Literal["none", "minor", "major", "critical"]
    direction: Literal["improved", "degraded", "unchanged"]

    @computed_field
    @property
    def is_statistically_significant(self) -> bool:
        """Return True if the p-value indicates statistical significance."""
        return self.p_value < 0.05

    @computed_field
    @property
    def is_practically_significant(self) -> bool:
        """Return True if Cohen's d indicates practical significance."""
        return self.cohens_d > 0.5

    def to_summary(self) -> str:
        """Generate a human-readable summary of the metric comparison.

        Returns:
            A summary string like "latency_p99 (api-service): 218ms vs baseline 185ms ± 12ms | p=0.003, d=0.72 | REGRESSION (major)"
        """
        status = "REGRESSION" if self.is_regression else self.direction.upper()
        severity_str = f" ({self.severity})" if self.is_regression else ""
        return (
            f"{self.metric_name} ({self.service}): {self.current_value:.0f} vs baseline "
            f"{self.baseline_mean:.0f} ± {self.baseline_stddev:.0f} | "
            f"p={self.p_value:.3f}, d={self.cohens_d:.2f} | {status}{severity_str}"
        )


class SLOCheck(BaseModel):
    """Whether a service-level objective is currently being met.

    Tracks SLO compliance and provides margin information to identify
    at-risk SLOs before they are violated.
    """

    model_config = ConfigDict(frozen=True)

    slo_name: str = Field(description="e.g., 'api-gateway P99 latency'")
    service: str
    target_description: str = Field(description="e.g., 'P99 < 200ms'")
    target_value: float
    current_value: float
    is_met: bool
    margin: float = Field(
        description="Distance from target. Positive = headroom, negative = violation"
    )

    @computed_field
    @property
    def is_at_risk(self) -> bool:
        """Return True if SLO is met but within 10% of being violated."""
        if not self.is_met:
            return False
        return self.margin < (self.target_value * 0.1)

    def to_summary(self) -> str:
        """Generate a human-readable summary of the SLO check.

        Returns:
            A summary string like "api-gateway P99 < 200ms: currently 185ms (15ms headroom)"
            or "api-gateway P99 < 200ms: currently 218ms (VIOLATED by 18ms)"
        """
        if self.is_met:
            return (
                f"\u2705 {self.slo_name} {self.target_description}: "
                f"currently {self.current_value:.0f} ({self.margin:.0f} headroom)"
            )
        else:
            return (
                f"\u274c {self.slo_name} {self.target_description}: "
                f"currently {self.current_value:.0f} (VIOLATED by {abs(self.margin):.0f})"
            )


class PerformanceAnalysisReport(BaseModel):
    """Complete output of the Performance Agent.

    Aggregates all benchmark results, metric comparisons, SLO checks,
    and provides an overall confidence score for the performance analysis.
    """

    model_config = ConfigDict(frozen=True)

    build_id: str
    comparisons: list[MetricComparison] = Field(default_factory=list)
    benchmarks: list[BenchmarkResult] = Field(default_factory=list)
    slo_checks: list[SLOCheck] = Field(default_factory=list)
    regressions_detected: int = Field(ge=0)
    anomalies_detected: int = Field(ge=0)
    missing_metrics: int = Field(
        ge=0, description="Metrics that could not be compared due to missing baseline data"
    )
    perf_confidence_score: int = Field(
        ge=0, le=100, description="0-100 confidence score. 100 = all clear, 0 = severe regressions"
    )
    summary: str
    timestamp: datetime

    @model_validator(mode="after")
    def validate_regressions_count(self) -> "PerformanceAnalysisReport":
        """Ensure regressions_detected matches the count of is_regression=True comparisons."""
        actual_regressions = sum(1 for c in self.comparisons if c.is_regression)
        if self.regressions_detected != actual_regressions:
            raise ValueError(
                f"regressions_detected ({self.regressions_detected}) must equal "
                f"count of comparisons with is_regression=True ({actual_regressions})"
            )
        return self

    @computed_field
    @property
    def has_slo_violations(self) -> bool:
        """Return True if any SLO check has is_met == False."""
        return any(not slo.is_met for slo in self.slo_checks)

    @computed_field
    @property
    def critical_regressions(self) -> list[MetricComparison]:
        """Return list of comparisons with critical severity."""
        return [c for c in self.comparisons if c.severity == "critical"]

    def to_summary(self) -> str:
        """Generate a human-readable summary of the performance analysis.

        Returns:
            A summary string like "Perf Analysis: 1 regression (major), 0 SLO violations, score: 55/100"
        """
        # Find the highest severity among regressions
        severity_order = {"critical": 4, "major": 3, "minor": 2, "none": 1}
        max_severity = "none"
        for c in self.comparisons:
            if c.is_regression and severity_order[c.severity] > severity_order[max_severity]:
                max_severity = c.severity

        severity_str = f" ({max_severity})" if self.regressions_detected > 0 else ""
        slo_violations = sum(1 for slo in self.slo_checks if not slo.is_met)

        return (
            f"Perf Analysis: {self.regressions_detected} regression{severity_str}, "
            f"{slo_violations} SLO violations, score: {self.perf_confidence_score}/100"
        )
