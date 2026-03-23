"""Conditional edge functions for the AI Release Guardian LangGraph workflow.

Each function inspects the current state and returns a string that tells
LangGraph which node to route to next. They are pure functions — no side
effects beyond logging.
"""

from typing import Literal

import structlog

from src.graph.state import GuardianState

logger = structlog.get_logger(__name__)


def should_proceed_to_risk(
    state: GuardianState,
) -> Literal["risk_scoring", "error_handler"]:
    """Conditional edge after parallel fan-out join.

    Checks whether BOTH the Test Analyst and Performance Agent produced
    valid reports. If either is missing, routes to the error handler.

    This is the fan-in synchronization point — LangGraph has already waited
    for both parallel nodes to complete before calling this function.
    """
    build_id = state.get("build_id", "unknown")
    has_test_report = state.get("test_report") is not None
    has_perf_report = state.get("perf_report") is not None
    has_errors = len(state.get("errors", [])) > 0

    logger.info(
        "edge.should_proceed_to_risk",
        build_id=build_id,
        has_test_report=has_test_report,
        has_perf_report=has_perf_report,
        has_errors=has_errors,
    )

    if has_test_report and has_perf_report and not has_errors:
        logger.info(
            "edge.route",
            build_id=build_id,
            message="Both reports present, proceeding to risk scoring",
            next="risk_scoring",
        )
        return "risk_scoring"

    if not has_test_report:
        logger.warning(
            "edge.missing_report",
            build_id=build_id,
            message="Test analysis report missing",
        )
    if not has_perf_report:
        logger.warning(
            "edge.missing_report",
            build_id=build_id,
            message="Performance analysis report missing",
        )
    if has_errors:
        logger.warning(
            "edge.errors_present",
            build_id=build_id,
            errors=state.get("errors", []),
        )

    logger.info(
        "edge.route",
        build_id=build_id,
        next="error_handler",
    )
    return "error_handler"


def should_proceed_to_decision(
    state: GuardianState,
) -> Literal["release_decision", "error_handler"]:
    """Conditional edge after risk scoring.

    Checks whether the Risk Scoring Agent produced a valid assessment.
    This is simpler than the first edge — only one upstream node to check.
    """
    build_id = state.get("build_id", "unknown")
    has_risk_assessment = state.get("risk_assessment") is not None
    has_new_errors = len(state.get("errors", [])) > 0

    if has_risk_assessment and not has_new_errors:
        logger.info(
            "edge.route",
            build_id=build_id,
            message="Risk assessment complete, proceeding to release decision",
            next="release_decision",
        )
        return "release_decision"

    logger.warning(
        "edge.route",
        build_id=build_id,
        message="Risk assessment missing or errors occurred",
        has_risk_assessment=has_risk_assessment,
        has_errors=has_new_errors,
        errors=state.get("errors", []),
        next="error_handler",
    )
    return "error_handler"


def route_after_decision(state: GuardianState) -> Literal["end"]:
    """Edge after release decision. Always routes to END.

    This exists as a named function (rather than a direct edge) so we
    could later add post-decision logic such as:
    - retrying on transient notification failures
    - triggering a rollback monitor after APPROVE
    - scheduling a follow-up check after REQUEST_REVIEW

    For now, it always returns 'end'.
    """
    build_id = state.get("build_id", "unknown")
    decision = state.get("release_decision")

    if decision:
        logger.info(
            "edge.route_after_decision",
            build_id=build_id,
            decision=decision.decision,
            risk_score=decision.risk_score,
            next="end",
        )

    return "end"
