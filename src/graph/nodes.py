"""LangGraph node functions for the AI Release Guardian workflow.

Each function is an async node that accepts the full GuardianState and returns
a PARTIAL state dict containing only the fields it populates. LangGraph merges
partials back into the shared state automatically.
"""

import asyncio
import time
from datetime import datetime

import structlog

from src.config import get_confidence_thresholds, get_policy, get_risk_weights
from src.graph.state import GuardianState
from src.models import (
    PerformanceAnalysisReport,
    ReleaseDecision,
    RiskAssessment,
    TestAnalysisReport,
)
from src.models.perf_report import BenchmarkResult, MetricComparison, SLOCheck
from src.models.release_decision import NotificationRecord, PolicyEvaluation
from src.models.risk_assessment import BlastRadius, HistoricalContext, RiskBreakdown
from src.models.test_report import CoverageReport, FailureClassification

logger = structlog.get_logger(__name__)


async def test_analyst_node(state: GuardianState) -> dict:
    """Runs the Test Analyst Agent. Produces a TestAnalysisReport.

    Stub implementation simulating the build-1847 scenario: 430/435 tests
    passed with 1 new bug, 1 flaky, and 1 infra failure classified.
    """
    build_id = state["build_id"]
    node = "test_analyst_node"
    start = time.monotonic()
    logger.info("node.enter", node=node, build_id=build_id)

    try:
        # Simulate real work (makes parallel execution visible in tests)
        await asyncio.sleep(0.5)

        classifications = [
            FailureClassification(
                test_id="test_payment_charge",
                test_name="test_payment_charge",
                category="new_bug",
                confidence=0.92,
                reasoning=(
                    "Stack trace shows a NullPointerException in PaymentService.charge() "
                    "introduced by the recent refactor. Not seen in previous 50 runs."
                ),
                classified_by="llm",
            ),
            FailureClassification(
                test_id="test_session_timeout",
                test_name="test_session_timeout",
                category="flaky",
                confidence=0.88,
                reasoning=(
                    "Test has a 45% historical flake rate due to race condition in "
                    "session expiry logic. Failure pattern matches known flaky signature."
                ),
                flake_rate=0.45,
                classified_by="algorithm",
            ),
            FailureClassification(
                test_id="test_external_api",
                test_name="test_external_api",
                category="infra",
                confidence=0.95,
                reasoning=(
                    "Connection timeout to external payment gateway. CI runner lost "
                    "network access momentarily. Unrelated to code changes in this commit."
                ),
                classified_by="llm",
            ),
        ]

        coverage = CoverageReport(
            total_lines=12400,
            covered_lines=10820,
            coverage_percentage=87.3,
            baseline_coverage=88.5,
            delta_from_baseline=-1.2,
        )

        report = TestAnalysisReport(
            build_id=build_id,
            total_tests=435,
            passed=430,
            failed=2,
            errored=1,
            skipped=2,
            failure_classifications=classifications,
            coverage=coverage,
            test_confidence_score=72,
            summary=(
                "430/435 passed. 1 new bug (test_payment_charge), "
                "1 flaky, 1 infra failure."
            ),
            timestamp=datetime.utcnow(),
        )

        duration = time.monotonic() - start
        logger.info("node.exit", node=node, build_id=build_id, duration_s=round(duration, 3))
        return {"test_report": report}

    except Exception as exc:
        duration = time.monotonic() - start
        logger.error(
            "node.error", node=node, build_id=build_id, error=str(exc), duration_s=round(duration, 3)
        )
        return {"errors": [f"{node}: {exc}"]}


async def performance_node(state: GuardianState) -> dict:
    """Runs the Performance Agent. Produces a PerformanceAnalysisReport.

    Stub implementation simulating a critical P99 latency regression on
    checkout-service: 318ms vs 189ms baseline (Cohen's d = 2.8).
    """
    build_id = state["build_id"]
    node = "performance_node"
    start = time.monotonic()
    logger.info("node.enter", node=node, build_id=build_id)

    try:
        await asyncio.sleep(0.5)

        benchmarks = [
            BenchmarkResult(
                service="checkout-service",
                endpoint="/api/v1/checkout",
                latency_p50_ms=48.0,
                latency_p95_ms=195.0,
                latency_p99_ms=318.0,
                throughput_rps=1150.0,
                memory_mb=512.0,
                error_rate=0.001,
                sample_count=1000,
            ),
        ]

        comparisons = [
            MetricComparison(
                metric_name="latency_p99",
                service="checkout-service",
                current_value=318.0,
                baseline_mean=189.6,
                baseline_stddev=15.0,
                baseline_sample_count=100,
                p_value=0.0001,
                cohens_d=2.8,
                is_regression=True,
                severity="critical",
                direction="degraded",
            ),
            MetricComparison(
                metric_name="latency_p50",
                service="checkout-service",
                current_value=48.0,
                baseline_mean=43.0,
                baseline_stddev=5.0,
                baseline_sample_count=100,
                p_value=0.22,
                cohens_d=0.3,
                is_regression=False,
                severity="none",
                direction="degraded",
            ),
            MetricComparison(
                metric_name="throughput_rps",
                service="checkout-service",
                current_value=1150.0,
                baseline_mean=1280.0,
                baseline_stddev=50.0,
                baseline_sample_count=100,
                p_value=0.08,
                cohens_d=0.4,
                is_regression=False,
                severity="none",
                direction="degraded",
            ),
        ]

        slo_checks = [
            SLOCheck(
                slo_name="checkout-service P99 latency",
                service="checkout-service",
                target_description="P99 < 250ms",
                target_value=250.0,
                current_value=318.0,
                is_met=False,
                margin=-68.0,
            ),
        ]

        report = PerformanceAnalysisReport(
            build_id=build_id,
            benchmarks=benchmarks,
            comparisons=comparisons,
            slo_checks=slo_checks,
            regressions_detected=1,
            anomalies_detected=0,
            missing_metrics=0,
            perf_confidence_score=55,
            summary=(
                "checkout-service P99 latency is 318ms (baseline 189ms). "
                "Critical regression detected. SLO P99 < 250ms is VIOLATED by 68ms."
            ),
            timestamp=datetime.utcnow(),
        )

        duration = time.monotonic() - start
        logger.info("node.exit", node=node, build_id=build_id, duration_s=round(duration, 3))
        return {"perf_report": report}

    except Exception as exc:
        duration = time.monotonic() - start
        logger.error(
            "node.error", node=node, build_id=build_id, error=str(exc), duration_s=round(duration, 3)
        )
        return {"errors": [f"{node}: {exc}"]}


async def risk_scoring_node(state: GuardianState) -> dict:
    """Runs the Risk Scoring Agent.

    Reads test_report and perf_report from state, computes a composite
    risk score from five weighted categories, and produces a RiskAssessment.
    Weights and confidence thresholds are loaded from src/config/risk_weights.yaml.
    """
    build_id = state["build_id"]
    node = "risk_scoring_node"
    start = time.monotonic()
    logger.info("node.enter", node=node, build_id=build_id)

    try:
        test_report = state["test_report"]
        perf_report = state["perf_report"]

        if test_report is None or perf_report is None:
            missing = []
            if test_report is None:
                missing.append("test_report")
            if perf_report is None:
                missing.append("perf_report")
            err = f"{node}: required inputs missing: {', '.join(missing)}"
            logger.error("node.missing_inputs", node=node, build_id=build_id, missing=missing)
            return {"errors": [err]}

        # Load weights and thresholds from config
        weights = get_risk_weights()
        thresholds = get_confidence_thresholds()

        # Derive component raw scores from agent confidence scores
        test_raw = float(100 - test_report.test_confidence_score)    # 28.0
        perf_raw = float(100 - perf_report.perf_confidence_score)    # 45.0

        components = [
            (
                "test_risk", test_raw, weights.test_risk,
                "1 new bug in test_payment_charge; coverage dropped 1.2%",
            ),
            (
                "performance_risk", perf_raw, weights.performance_risk,
                "Critical P99 regression: 318ms vs 189ms baseline; SLO violated",
            ),
            (
                "blast_radius_risk", 35.0, weights.blast_radius_risk,
                "3 services affected including critical payment-service",
            ),
            (
                "historical_risk", 30.0, weights.historical_risk,
                "10% rollback rate over last 20 deploys; 1 recent incident",
            ),
            (
                "change_velocity_risk", 20.0, weights.change_velocity_risk,
                "Normal commit velocity; no merge-train congestion detected",
            ),
        ]

        risk_breakdown = [
            RiskBreakdown(
                category=category,
                raw_score=raw,
                weight=weight,
                weighted_score=round(raw * weight, 2),
                details=details,
            )
            for category, raw, weight, details in components
        ]

        composite_risk_score = round(sum(rb.weighted_score for rb in risk_breakdown))
        confidence_level = thresholds.get_level(composite_risk_score)

        blast_radius = BlastRadius(
            files_changed=12,
            services_affected=["checkout-service", "payment-service", "user-service"],
            critical_services_affected=["payment-service"],
            downstream_dependencies=["order-service", "notification-service"],
            estimated_users_affected=15000,
        )

        historical_context = HistoricalContext(
            service="checkout-service",
            total_deployments_analyzed=20,
            rollback_count=2,
            rollback_rate=0.10,
            incident_count=1,
            avg_recovery_time_minutes=22.5,
            similar_change_outcomes=["success", "success", "rollback", "success"],
            last_rollback_days_ago=14,
        )

        assessment = RiskAssessment(
            build_id=build_id,
            composite_risk_score=composite_risk_score,
            confidence_level=confidence_level,
            risk_breakdown=risk_breakdown,
            blast_radius=blast_radius,
            historical_context=historical_context,
            narrative=(
                f"Build {build_id} carries {confidence_level} risk "
                f"(score {composite_risk_score}/100). "
                "The dominant concern is a critical P99 latency regression on checkout-service "
                "(318ms vs 189ms baseline, Cohen's d=2.8), which violates the SLO by 68ms. "
                "A new bug in test_payment_charge adds further confidence risk. "
                "Payment-service is in the blast radius, warranting careful review before promoting."
            ),
            recommended_actions=[
                "Investigate NullPointerException in PaymentService.charge() before promoting.",
                "Profile checkout-service for the P99 regression root cause.",
                "Confirm payment-service health in staging before any production deploy.",
            ],
            timestamp=datetime.utcnow(),
        )

        duration = time.monotonic() - start
        logger.info(
            "node.exit",
            node=node,
            build_id=build_id,
            composite_risk_score=composite_risk_score,
            confidence_level=confidence_level,
            duration_s=round(duration, 3),
        )
        return {"risk_assessment": assessment}

    except Exception as exc:
        duration = time.monotonic() - start
        logger.error(
            "node.error", node=node, build_id=build_id, error=str(exc), duration_s=round(duration, 3)
        )
        return {"errors": [f"{node}: {exc}"]}


async def release_decision_node(state: GuardianState) -> dict:
    """Runs the Release Decision Agent.

    Reads risk_assessment from state and applies environment-specific
    thresholds (loaded from release_policies.yaml) to produce the final
    ReleaseDecision with notifications.
    """
    build_id = state["build_id"]
    node = "release_decision_node"
    start = time.monotonic()
    logger.info("node.enter", node=node, build_id=build_id)

    try:
        risk_assessment = state["risk_assessment"]
        if risk_assessment is None:
            err = f"{node}: risk_assessment is required but was None"
            logger.error("node.missing_inputs", node=node, build_id=build_id)
            return {"errors": [err]}

        environment = state["environment"]
        score = risk_assessment.composite_risk_score
        confidence_level = risk_assessment.confidence_level

        # Load policy thresholds and deployment-window rules from config
        policy = get_policy(environment)
        can_deploy, block_reason = policy.can_deploy_now()
        freeze_ok = not policy.is_in_freeze()[0]

        if not can_deploy:
            raw_decision = "BLOCK"
            pipeline_action = "abort"
            rationale = f"Deployment blocked: {block_reason}"
            notification_type = "block"
        elif score <= policy.risk_threshold_approve:
            raw_decision = "APPROVE"
            pipeline_action = "proceed"
            rationale = (
                f"Risk score {score}/100 ({confidence_level}) is within the "
                f"{environment} approval threshold (≤{policy.risk_threshold_approve}). "
                "Automated approval granted."
            )
            notification_type = "approval"
        elif score <= policy.risk_threshold_review:
            raw_decision = "REQUEST_REVIEW"
            pipeline_action = "hold"
            rationale = (
                f"Risk score {score}/100 ({confidence_level}) exceeds auto-approve "
                f"threshold (>{policy.risk_threshold_approve}) but is within review range "
                f"(≤{policy.risk_threshold_review}). Human review required before promoting."
            )
            notification_type = "review_request"
        else:
            raw_decision = "BLOCK"
            pipeline_action = "abort"
            rationale = (
                f"Risk score {score}/100 ({confidence_level}) exceeds the "
                f"{environment} maximum threshold (>{policy.risk_threshold_review}). "
                "Deployment blocked automatically."
            )
            notification_type = "block"

        policy_eval = PolicyEvaluation(
            environment=environment,
            policy_version="1.0",
            risk_threshold_approve=policy.risk_threshold_approve,
            risk_threshold_review=policy.risk_threshold_review,
            actual_risk_score=score,
            deployment_window_ok=can_deploy,
            freeze_period_ok=freeze_ok,
            overrides_applied=[],
            raw_decision=raw_decision,
            final_decision=raw_decision,
        )

        now = datetime.utcnow()
        notifications = [
            NotificationRecord(
                channel="slack",
                recipient="#releases",
                message_type=notification_type,
                sent_at=now,
                success=True,
            ),
            NotificationRecord(
                channel="github_status",
                recipient="commit-status-api",
                message_type=notification_type,
                sent_at=now,
                success=True,
            ),
        ]

        decision = ReleaseDecision(
            build_id=build_id,
            commit_sha=state["commit_sha"],
            decision=raw_decision,
            risk_score=score,
            confidence_level=confidence_level,
            rationale=rationale,
            policy_evaluation=policy_eval,
            pipeline_action_taken=pipeline_action,
            notifications=notifications,
            timestamp=now,
        )

        duration = time.monotonic() - start
        logger.info(
            "node.exit",
            node=node,
            build_id=build_id,
            decision=raw_decision,
            pipeline_action=pipeline_action,
            duration_s=round(duration, 3),
        )
        return {"release_decision": decision}

    except Exception as exc:
        duration = time.monotonic() - start
        logger.error(
            "node.error", node=node, build_id=build_id, error=str(exc), duration_s=round(duration, 3)
        )
        return {"errors": [f"{node}: {exc}"]}


async def error_handler_node(state: GuardianState) -> dict:
    """Handles errors from any stage. Safety fallback that always BLOCKs.

    Logs every accumulated error and produces a BLOCK ReleaseDecision so
    the pipeline is never silently approved when the workflow had failures.
    """
    build_id = state["build_id"]
    node = "error_handler_node"
    start = time.monotonic()
    logger.info("node.enter", node=node, build_id=build_id)

    errors = state.get("errors") or []
    for err in errors:
        logger.error("pipeline.error", node=node, build_id=build_id, error=err)

    joined_errors = "; ".join(errors) if errors else "unknown pipeline error"
    environment = state["environment"]
    now = datetime.utcnow()

    # Minimal policy evaluation record for the safety-fallback block
    policy_eval = PolicyEvaluation(
        environment=environment,
        policy_version="1.0",
        risk_threshold_approve=25,
        risk_threshold_review=50,
        actual_risk_score=100,
        deployment_window_ok=False,
        freeze_period_ok=True,
        overrides_applied=["pipeline-error-safety-block"],
        raw_decision="BLOCK",
        final_decision="BLOCK",
    )

    decision = ReleaseDecision(
        build_id=build_id,
        commit_sha=state["commit_sha"],
        decision="BLOCK",
        risk_score=100,
        confidence_level="CRITICAL",
        rationale=f"Blocked due to pipeline errors: {joined_errors}",
        policy_evaluation=policy_eval,
        pipeline_action_taken="abort",
        notifications=[],
        timestamp=now,
    )

    duration = time.monotonic() - start
    logger.info(
        "node.exit",
        node=node,
        build_id=build_id,
        error_count=len(errors),
        duration_s=round(duration, 3),
    )
    return {"release_decision": decision}
