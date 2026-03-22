"""Graph state definitions."""

import operator
from typing import Annotated, TypedDict

from src.models import (
    PerformanceAnalysisReport,
    ReleaseDecision,
    RiskAssessment,
    TestAnalysisReport,
)


class GuardianState(TypedDict):
    """Shared state object that flows through the entire LangGraph workflow.

    Each agent node reads what it needs and writes its output to the
    appropriate field. Fields are populated incrementally as the graph
    executes.

    Notes:
        - The ``errors`` field uses ``Annotated[list[str], operator.add]``,
          which is a LangGraph reducer. This means errors from parallel nodes
          get MERGED (appended) rather than overwritten — so no error is lost
          when multiple nodes run concurrently.
        - ``metadata`` is a flexible dict for passing extra context that
          doesn't fit a typed field, e.g. manual override info, retry counts,
          or feature flags injected at runtime.
    """

    build_id: str
    commit_sha: str
    branch: str
    environment: str
    test_report: TestAnalysisReport | None
    perf_report: PerformanceAnalysisReport | None
    risk_assessment: RiskAssessment | None
    release_decision: ReleaseDecision | None
    errors: Annotated[list[str], operator.add]
    metadata: dict


def create_initial_state(
    build_id: str,
    commit_sha: str,
    branch: str = "main",
    environment: str = "staging",
) -> GuardianState:
    """Creates the initial state that kicks off the workflow."""
    return GuardianState(
        build_id=build_id,
        commit_sha=commit_sha,
        branch=branch,
        environment=environment,
        test_report=None,
        perf_report=None,
        risk_assessment=None,
        release_decision=None,
        errors=[],
        metadata={},
    )
