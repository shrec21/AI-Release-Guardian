"""Data models module.

This module re-exports all Pydantic models for easy importing:
    from src.models import BuildInfo, TestAnalysisReport, RiskAssessment, ...
"""

from src.models.build_metadata import BuildInfo, GitDiff, PipelineStatus
from src.models.perf_report import (
    BenchmarkResult,
    MetricComparison,
    PerformanceAnalysisReport,
    SLOCheck,
)
from src.models.release_decision import (
    AuditRecord,
    NotificationRecord,
    PolicyEvaluation,
    ReleaseDecision,
)
from src.models.risk_assessment import (
    BlastRadius,
    HistoricalContext,
    RiskAssessment,
    RiskBreakdown,
)
from src.models.test_report import (
    CoverageReport,
    FailureClassification,
    TestAnalysisReport,
    TestResult,
)

__all__ = [
    # build_metadata
    "BuildInfo",
    "GitDiff",
    "PipelineStatus",
    # test_report
    "TestResult",
    "FailureClassification",
    "CoverageReport",
    "TestAnalysisReport",
    # perf_report
    "BenchmarkResult",
    "MetricComparison",
    "SLOCheck",
    "PerformanceAnalysisReport",
    # risk_assessment
    "RiskBreakdown",
    "BlastRadius",
    "HistoricalContext",
    "RiskAssessment",
    # release_decision
    "NotificationRecord",
    "PolicyEvaluation",
    "ReleaseDecision",
    "AuditRecord",
]
