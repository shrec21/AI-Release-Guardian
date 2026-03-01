#!/usr/bin/env python3
"""Verification script for all Pydantic models.

This script creates instances of every model with realistic sample data
from the checkout-service scenario (build-1847) and verifies they work correctly.

Run with:
    python -m scripts.verify_models
    python scripts/verify_models.py
"""

import sys
import traceback
from datetime import datetime, timezone

# Add project root to path for direct script execution
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import (
    # build_metadata
    BuildInfo,
    GitDiff,
    PipelineStatus,
    # test_report
    TestResult,
    FailureClassification,
    CoverageReport,
    TestAnalysisReport,
    # perf_report
    BenchmarkResult,
    MetricComparison,
    SLOCheck,
    PerformanceAnalysisReport,
    # risk_assessment
    RiskBreakdown,
    BlastRadius,
    HistoricalContext,
    RiskAssessment,
    # release_decision
    NotificationRecord,
    PolicyEvaluation,
    ReleaseDecision,
    AuditRecord,
)


def create_sample_data() -> AuditRecord:
    """Create a complete chain of models with realistic checkout-service scenario data."""

    now = datetime.now(timezone.utc)

    # =========================================================================
    # 1. Build Metadata
    # =========================================================================

    git_diff = GitDiff(
        files_added=["src/checkout/fraud_check.py"],
        files_modified=[
            "src/checkout/payment.py",
            "src/checkout/cart.py",
            "src/api/endpoints.py",
        ],
        files_deleted=[],
        total_lines_changed=247,
        affected_services=["checkout-service", "payment-service", "api-gateway"],
    )
    print(f"GitDiff.total_files_changed: {git_diff.total_files_changed}")
    print(f"GitDiff.involves_service('payment-service'): {git_diff.involves_service('payment-service')}")

    pipeline_stages = [
        PipelineStatus(stage="build", status="success", duration_seconds=45.2, started_at=now, finished_at=now),
        PipelineStatus(stage="test", status="success", duration_seconds=312.8, started_at=now, finished_at=now),
        PipelineStatus(stage="deploy", status="pending", duration_seconds=None, started_at=None, finished_at=None),
    ]

    build_info = BuildInfo(
        build_id="build-1847",
        commit_sha="a1b2c3d4e5f6789012345678901234567890abcd",
        branch="main",
        pipeline="checkout-service-ci",
        trigger="push",
        timestamp=now,
        files_changed=["src/checkout/payment.py", "src/checkout/cart.py", "src/api/endpoints.py", "src/checkout/fraud_check.py"],
        authors=["alice@company.com", "bob@company.com"],
        git_diff=git_diff,
        pipeline_stages=pipeline_stages,
    )
    print(f"\nBuildInfo.to_summary(): {build_info.to_summary()}")
    print(f"BuildInfo.is_main_branch(): {build_info.is_main_branch()}")

    # =========================================================================
    # 2. Test Results (435 tests, 3 failures)
    # =========================================================================

    # Create 3 failed test results
    test_results = [
        TestResult(
            test_id="test-001",
            test_name="test_payment_charge_insufficient_funds",
            suite="PaymentSuite",
            status="failed",
            duration_ms=1234.5,
            error_message="NullPointerException",
            stack_trace="at PaymentService.charge(Payment.java:42)\nat ...",
            retry_count=0,
        ),
        TestResult(
            test_id="test-002",
            test_name="test_cart_timeout",
            suite="CartSuite",
            status="failed",
            duration_ms=5000.0,
            error_message="TimeoutError: Connection timed out",
            stack_trace="at CartService.connect(Cart.java:88)\nat ...",
            retry_count=2,
        ),
        TestResult(
            test_id="test-003",
            test_name="test_fraud_detection_edge_case",
            suite="FraudSuite",
            status="error",
            duration_ms=234.1,
            error_message="AssertionError: Expected fraud score > 0.8",
            stack_trace="at FraudDetector.analyze(Fraud.java:156)\nat ...",
            retry_count=0,
        ),
    ]

    for tr in test_results:
        print(f"\nTestResult.to_summary(): {tr.to_summary()}")
        print(f"TestResult.is_failure: {tr.is_failure}")

    # =========================================================================
    # 3. Failure Classifications (1 new_bug, 1 flaky, 1 infra)
    # =========================================================================

    failure_classifications = [
        FailureClassification(
            test_id="test-001",
            test_name="test_payment_charge_insufficient_funds",
            category="new_bug",
            confidence=0.92,
            reasoning="New code path introduced in payment.py line 42 causes NPE when funds are insufficient. No historical flakiness detected.",
            flake_rate=None,
            classified_by="llm",
        ),
        FailureClassification(
            test_id="test-002",
            test_name="test_cart_timeout",
            category="flaky",
            confidence=0.87,
            reasoning="This test has failed 12 times in the last 100 runs due to network timeouts. Infrastructure-related intermittent failure.",
            flake_rate=0.12,
            classified_by="algorithm",
        ),
        FailureClassification(
            test_id="test-003",
            test_name="test_fraud_detection_edge_case",
            category="infra",
            confidence=0.78,
            reasoning="ML model endpoint was unavailable during test. This is an infrastructure issue, not a code bug.",
            flake_rate=0.05,
            classified_by="llm",
        ),
    ]

    # =========================================================================
    # 4. Coverage Report (87.3%, -1.2% delta)
    # =========================================================================

    coverage = CoverageReport(
        total_lines=15420,
        covered_lines=13462,
        coverage_percentage=87.3,
        baseline_coverage=88.5,
        delta_from_baseline=-1.2,
        uncovered_critical_paths=["src/checkout/fraud_check.py:handle_edge_case"],
    )
    print(f"\nCoverageReport.is_coverage_regression: {coverage.is_coverage_regression}")

    # =========================================================================
    # 5. Test Analysis Report (score: 72)
    # =========================================================================

    test_report = TestAnalysisReport(
        build_id="build-1847",
        total_tests=435,
        passed=430,
        failed=2,
        skipped=2,
        errored=1,
        failure_classifications=failure_classifications,
        coverage=coverage,
        test_confidence_score=72,
        summary="435 tests executed. 2 failures (1 new bug, 1 flaky), 1 error (infra). Coverage dropped 1.2% below baseline.",
        timestamp=now,
    )
    print(f"\nTestAnalysisReport.to_summary(): {test_report.to_summary()}")
    print(f"TestAnalysisReport.new_bugs_count: {test_report.new_bugs_count}")
    print(f"TestAnalysisReport.has_critical_failures: {test_report.has_critical_failures}")

    # =========================================================================
    # 6. Benchmark Result (P99: 318ms)
    # =========================================================================

    benchmark = BenchmarkResult(
        service="checkout-service",
        endpoint="/api/v1/checkout",
        latency_p50_ms=45.2,
        latency_p95_ms=189.5,
        latency_p99_ms=318.0,
        throughput_rps=1250.0,
        memory_mb=512.4,
        error_rate=0.002,
        sample_count=10000,
    )
    print(f"\nBenchmarkResult.to_summary(): {benchmark.to_summary()}")

    # =========================================================================
    # 7. Metric Comparison (P99 regression, p=0.0001, d=2.8)
    # =========================================================================

    metric_comparison = MetricComparison(
        metric_name="latency_p99",
        service="checkout-service",
        current_value=318.0,
        baseline_mean=185.0,
        baseline_stddev=12.3,
        baseline_sample_count=500,
        p_value=0.0001,
        cohens_d=2.8,
        is_regression=True,
        severity="major",
        direction="degraded",
    )
    print(f"\nMetricComparison.to_summary(): {metric_comparison.to_summary()}")
    print(f"MetricComparison.is_statistically_significant: {metric_comparison.is_statistically_significant}")
    print(f"MetricComparison.is_practically_significant: {metric_comparison.is_practically_significant}")

    # =========================================================================
    # 8. SLO Check (P99 < 250ms violated)
    # =========================================================================

    slo_check = SLOCheck(
        slo_name="checkout-service",
        service="checkout-service",
        target_description="P99 < 250ms",
        target_value=250.0,
        current_value=318.0,
        is_met=False,
        margin=-68.0,
    )
    print(f"\nSLOCheck.to_summary(): {slo_check.to_summary()}")
    print(f"SLOCheck.is_at_risk: {slo_check.is_at_risk}")

    # =========================================================================
    # 9. Performance Analysis Report (score: 55)
    # =========================================================================

    perf_report = PerformanceAnalysisReport(
        build_id="build-1847",
        comparisons=[metric_comparison],
        benchmarks=[benchmark],
        slo_checks=[slo_check],
        regressions_detected=1,
        anomalies_detected=0,
        missing_metrics=0,
        perf_confidence_score=55,
        summary="1 major regression detected in P99 latency. SLO violated: checkout-service P99 exceeded 250ms target.",
        timestamp=now,
    )
    print(f"\nPerformanceAnalysisReport.to_summary(): {perf_report.to_summary()}")
    print(f"PerformanceAnalysisReport.has_slo_violations: {perf_report.has_slo_violations}")
    print(f"PerformanceAnalysisReport.critical_regressions: {perf_report.critical_regressions}")

    # =========================================================================
    # 10. Blast Radius (3 services, 1 critical)
    # =========================================================================

    blast_radius = BlastRadius(
        files_changed=4,
        services_affected=["checkout-service", "payment-service", "api-gateway"],
        critical_services_affected=["payment-service"],
        downstream_dependencies=["notification-service", "analytics-service", "billing-service", "audit-service", "reporting-service"],
        estimated_users_affected=50000,
    )
    print(f"\nBlastRadius.to_summary(): {blast_radius.to_summary()}")
    print(f"BlastRadius.total_impact_zone: {blast_radius.total_impact_zone}")
    print(f"BlastRadius.involves_critical_path: {blast_radius.involves_critical_path}")
    print(f"BlastRadius.scope: {blast_radius.scope}")

    # =========================================================================
    # 11. Historical Context (2 rollbacks in 20 deploys)
    # =========================================================================

    historical_context = HistoricalContext(
        service="checkout-service",
        total_deployments_analyzed=20,
        rollback_count=2,
        rollback_rate=0.10,
        incident_count=1,
        avg_recovery_time_minutes=15.5,
        similar_change_outcomes=["success", "success", "rollback", "success"],
        last_rollback_days_ago=12,
    )
    print(f"\nHistoricalContext.to_summary(): {historical_context.to_summary()}")
    print(f"HistoricalContext.is_high_risk_service: {historical_context.is_high_risk_service}")

    # =========================================================================
    # 12. Risk Breakdowns (5 categories, proper weights summing to ~33)
    # =========================================================================

    # Weights: test=0.30, perf=0.25, blast=0.20, historical=0.15, velocity=0.10
    # Target composite score: ~33

    risk_breakdowns = [
        RiskBreakdown(
            category="test_risk",
            raw_score=28.0,
            weight=0.30,
            weighted_score=8.4,  # 28 * 0.30 = 8.4
            details="1 new bug detected in payment flow, coverage dropped 1.2%",
        ),
        RiskBreakdown(
            category="performance_risk",
            raw_score=54.0,
            weight=0.25,
            weighted_score=13.5,  # 54 * 0.25 = 13.5
            details="P99 latency regression: 318ms vs 185ms baseline, SLO violated",
        ),
        RiskBreakdown(
            category="blast_radius_risk",
            raw_score=35.0,
            weight=0.20,
            weighted_score=7.0,  # 35 * 0.20 = 7.0
            details="3 services affected (1 critical: payment-service), 5 downstream",
        ),
        RiskBreakdown(
            category="historical_risk",
            raw_score=20.0,
            weight=0.15,
            weighted_score=3.0,  # 20 * 0.15 = 3.0
            details="2 rollbacks in last 20 deploys (10%), last rollback 12 days ago",
        ),
        RiskBreakdown(
            category="change_velocity_risk",
            raw_score=10.0,
            weight=0.10,
            weighted_score=1.0,  # 10 * 0.10 = 1.0
            details="Normal change velocity, 4 files changed by 2 authors",
        ),
    ]

    for rb in risk_breakdowns:
        print(f"\nRiskBreakdown.to_summary(): {rb.to_summary()}")

    # Total: 8.4 + 13.5 + 7.0 + 3.0 + 1.0 = 32.9 ≈ 33

    # =========================================================================
    # 13. Risk Assessment (composite score: 33, MEDIUM confidence)
    # =========================================================================

    risk_assessment = RiskAssessment(
        build_id="build-1847",
        composite_risk_score=33,
        confidence_level="MEDIUM",
        risk_breakdown=risk_breakdowns,
        blast_radius=blast_radius,
        historical_context=historical_context,
        narrative="This release carries moderate risk due to a significant P99 latency regression that violates the checkout SLO. "
                  "While test coverage shows only one new bug (payment edge case), the performance degradation affects 50K users. "
                  "The blast radius includes payment-service, a critical path. Historical data shows acceptable rollback rate.",
        recommended_actions=[
            "Investigate P99 latency regression in checkout-service before proceeding",
            "Review payment edge case fix with senior engineer",
            "Consider canary deployment to limit blast radius",
        ],
        timestamp=now,
    )
    print(f"\nRiskAssessment.to_summary(): {risk_assessment.to_summary()}")
    print(f"RiskAssessment.is_auto_approvable: {risk_assessment.is_auto_approvable}")
    print(f"RiskAssessment.requires_block: {risk_assessment.requires_block}")
    print(f"RiskAssessment.top_risk_factor: {risk_assessment.top_risk_factor.category if risk_assessment.top_risk_factor else None}")

    # =========================================================================
    # 14. Policy Evaluation (production, threshold 25, score 33 → REQUEST_REVIEW)
    # =========================================================================

    policy_evaluation = PolicyEvaluation(
        environment="production",
        policy_version="1.0",
        risk_threshold_approve=25,
        risk_threshold_review=50,
        actual_risk_score=33,
        deployment_window_ok=True,
        freeze_period_ok=True,
        overrides_applied=[],
        raw_decision="REQUEST_REVIEW",
        final_decision="REQUEST_REVIEW",
    )
    print(f"\nPolicyEvaluation.to_summary(): {policy_evaluation.to_summary()}")
    print(f"PolicyEvaluation.was_overridden: {policy_evaluation.was_overridden}")

    # =========================================================================
    # 15. Notifications
    # =========================================================================

    notifications = [
        NotificationRecord(
            channel="slack",
            recipient="#releases",
            message_type="review_request",
            sent_at=now,
            success=True,
            error=None,
        ),
        NotificationRecord(
            channel="github_status",
            recipient="PR #1847",
            message_type="review_request",
            sent_at=now,
            success=True,
            error=None,
        ),
    ]

    # =========================================================================
    # 16. Release Decision (REQUEST_REVIEW, pipeline held)
    # =========================================================================

    release_decision = ReleaseDecision(
        build_id="build-1847",
        commit_sha="a1b2c3d4e5f6789012345678901234567890abcd",
        decision="REQUEST_REVIEW",
        risk_score=33,
        confidence_level="MEDIUM",
        rationale="Release requires human review due to P99 latency regression exceeding SLO threshold. "
                  "Risk score 33/100 exceeds auto-approve threshold of 25 but is below block threshold of 50.",
        policy_evaluation=policy_evaluation,
        manual_override=False,
        overridden_by=None,
        override_reason=None,
        pipeline_action_taken="hold",
        notifications=notifications,
        timestamp=now,
    )
    print(f"\nReleaseDecision.to_summary(): {release_decision.to_summary()}")
    print(f"ReleaseDecision.notification_channels: {release_decision.notification_channels}")
    print(f"ReleaseDecision.all_notifications_succeeded: {release_decision.all_notifications_succeeded}")

    # =========================================================================
    # 17. Audit Record (complete with all snapshots)
    # =========================================================================

    audit_record = AuditRecord(
        decision_id="audit-7f3e2a1b-9c8d-4e5f-a6b7-c8d9e0f1a2b3",
        build_id="build-1847",
        commit_sha="a1b2c3d4e5f6789012345678901234567890abcd",
        environment="production",
        decision=release_decision,
        test_report_snapshot=test_report,
        perf_report_snapshot=perf_report,
        risk_assessment_snapshot=risk_assessment,
        graph_execution_time_seconds=24.5,
        agent_timings={
            "test_analyst": 12.3,
            "performance": 8.7,
            "risk_scoring": 2.1,
            "release_decision": 1.4,
        },
        errors_encountered=[],
        created_at=now,
    )
    print(f"\nAuditRecord.to_summary(): {audit_record.to_summary()}")
    print(f"AuditRecord.had_errors: {audit_record.had_errors}")
    print(f"AuditRecord.is_complete: {audit_record.is_complete}")

    return audit_record


def main() -> None:
    """Run the verification script."""
    print("=" * 80)
    print("AI Release Guardian - Model Verification Script")
    print("=" * 80)
    print("\nScenario: checkout-service build-1847")
    print("  - 435 tests, 3 failures (1 new bug, 1 flaky, 1 infra)")
    print("  - P99 latency regression: 318ms vs 185ms baseline")
    print("  - SLO violated: P99 < 250ms")
    print("  - 3 services affected (1 critical: payment-service)")
    print("  - Risk score: 33/100 (MEDIUM) → REQUEST_REVIEW")
    print("=" * 80)

    try:
        audit_record = create_sample_data()

        print("\n" + "=" * 80)
        print("FULL AUDIT RECORD JSON:")
        print("=" * 80)
        print(audit_record.model_dump_json(indent=2))

        print("\n" + "=" * 80)
        print("\u2705 All 16 models verified successfully")
        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"\u274c VERIFICATION FAILED: {type(e).__name__}: {e}")
        print("=" * 80)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
