"""Test report data models.

This module contains Pydantic models for representing test results,
failure classifications, coverage reports, and complete test analysis
outputs from the Test Analyst Agent.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class TestResult(BaseModel):
    """A single test case result from CI output (parsed from JUnit XML / pytest JSON).

    Represents the outcome of an individual test execution including
    timing, status, and error details if applicable.
    """

    model_config = ConfigDict(frozen=True)

    test_id: str
    test_name: str
    suite: str = Field(description="The test suite/class this test belongs to")
    status: Literal["passed", "failed", "skipped", "error"]
    duration_ms: float = Field(ge=0, description="Test execution time in milliseconds")
    error_message: str | None = None
    stack_trace: str | None = None
    retry_count: int = Field(default=0, ge=0)

    @computed_field
    @property
    def is_failure(self) -> bool:
        """Return True if the test failed or errored."""
        return self.status in ("failed", "error")

    def to_summary(self) -> str:
        """Generate a human-readable summary of the test result.

        Returns:
            A summary string like "FAILED: test_payment_charge (PaymentSuite) - NullPointerException"
        """
        status_str = self.status.upper()
        summary = f"{status_str}: {self.test_name} ({self.suite})"
        if self.error_message:
            summary += f" - {self.error_message}"
        return summary


class FailureClassification(BaseModel):
    """LLM or algorithm classification of why a test failed.

    Provides categorization of test failures to help determine if they
    represent real bugs, flaky tests, infrastructure issues, or known problems.
    """

    model_config = ConfigDict(frozen=True)

    test_id: str
    test_name: str
    category: Literal["new_bug", "flaky", "infra", "known_issue"]
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence 0-1")
    reasoning: str = Field(description="Explanation of why this category was chosen")
    flake_rate: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Historical flake rate if available"
    )
    classified_by: Literal["algorithm", "llm"] = Field(
        default="llm",
        description="Tracks whether classification came from flaky-detection algorithm or LLM",
    )


class CoverageReport(BaseModel):
    """Code coverage comparison against baseline.

    Tracks code coverage metrics and compares them against a baseline
    to detect coverage regressions.
    """

    model_config = ConfigDict(frozen=True)

    total_lines: int = Field(ge=0)
    covered_lines: int = Field(ge=0)
    coverage_percentage: float = Field(ge=0.0, le=100.0)
    baseline_coverage: float = Field(ge=0.0, le=100.0)
    delta_from_baseline: float = Field(
        description="Coverage change from baseline. Positive = improvement, negative = regression"
    )
    uncovered_critical_paths: list[str] = Field(default_factory=list)

    @field_validator("covered_lines")
    @classmethod
    def covered_lines_must_not_exceed_total(cls, v: int, info) -> int:
        """Ensure covered_lines does not exceed total_lines."""
        total_lines = info.data.get("total_lines")
        if total_lines is not None and v > total_lines:
            raise ValueError("covered_lines cannot exceed total_lines")
        return v

    @computed_field
    @property
    def is_coverage_regression(self) -> bool:
        """Return True if coverage dropped more than 1% from baseline."""
        return self.delta_from_baseline < -1.0


class TestAnalysisReport(BaseModel):
    """Complete output of the Test Analyst Agent.

    Aggregates all test results, failure classifications, coverage data,
    and provides an overall confidence score for the test analysis.
    """

    model_config = ConfigDict(frozen=True)

    build_id: str
    total_tests: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errored: int = Field(ge=0)
    failure_classifications: list[FailureClassification] = Field(default_factory=list)
    coverage: CoverageReport | None = None
    test_confidence_score: int = Field(
        ge=0, le=100, description="0-100 confidence score. 100 = all clear, 0 = catastrophic"
    )
    summary: str
    timestamp: datetime

    @field_validator("passed", "failed", "skipped", "errored")
    @classmethod
    def validate_test_counts_sum(cls, v: int, info) -> int:
        """Validate that test counts sum to total_tests.

        This validator runs after all count fields are set and checks
        that they sum correctly to total_tests.
        """
        data = info.data
        # Only validate when all required fields are present
        if all(key in data for key in ("total_tests", "passed", "failed", "skipped", "errored")):
            total = data["passed"] + data["failed"] + data["skipped"] + data["errored"]
            if total != data["total_tests"]:
                raise ValueError(
                    f"Test counts must sum to total_tests: "
                    f"{data['passed']} + {data['failed']} + {data['skipped']} + {data['errored']} "
                    f"= {total} != {data['total_tests']}"
                )
        return v

    @computed_field
    @property
    def new_bugs_count(self) -> int:
        """Return the count of failures classified as new bugs."""
        return sum(1 for fc in self.failure_classifications if fc.category == "new_bug")

    @computed_field
    @property
    def has_critical_failures(self) -> bool:
        """Return True if there are any new bugs detected."""
        return self.new_bugs_count > 0

    def to_summary(self) -> str:
        """Generate a human-readable summary of the test analysis.

        Returns:
            A summary string like "Test Analysis: 430/435 passed, 2 new bugs, 1 flaky, score: 72/100"
        """
        flaky_count = sum(1 for fc in self.failure_classifications if fc.category == "flaky")
        return (
            f"Test Analysis: {self.passed}/{self.total_tests} passed, "
            f"{self.new_bugs_count} new bugs, {flaky_count} flaky, "
            f"score: {self.test_confidence_score}/100"
        )
