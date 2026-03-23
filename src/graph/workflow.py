"""LangGraph workflow definition."""

import asyncio

import structlog
from langgraph.graph import END, START, StateGraph

from src.graph.edges import route_after_decision, should_proceed_to_decision
from src.graph.nodes import (
    error_handler_node,
    performance_node,
    release_decision_node,
    risk_scoring_node,
    test_analyst_node,
)
from src.graph.state import GuardianState, create_initial_state

logger = structlog.get_logger(__name__)


def build_guardian_graph() -> StateGraph:
    """Constructs the AI Release Guardian workflow graph.

    Topology:
        START ──→ test_analyst ──┐
                                 ├──→ risk_scoring ──→ should_proceed_to_decision ──→ release_decision ──→ END
        START ──→ performance ───┘                 └──→ error_handler ──────────────────────────────────→ END

    Fan-out:
        test_analyst and performance both receive edges from START and run
        in parallel. LangGraph executes them concurrently.

    Fan-in:
        Both parallel nodes have a direct edge into risk_scoring. LangGraph
        waits for ALL incoming edges to be satisfied before executing a node,
        so risk_scoring only runs once both reports are in state.

    Error handling:
        risk_scoring internally validates that both reports are present. If
        either is missing it appends to state["errors"] and returns an empty
        dict. should_proceed_to_decision then sees a missing risk_assessment
        and routes to error_handler, which always produces a BLOCK decision.
    """
    workflow = StateGraph(GuardianState)

    # ── Nodes ────────────────────────────────────────────────────────────────
    workflow.add_node("test_analyst", test_analyst_node)
    workflow.add_node("performance", performance_node)
    workflow.add_node("risk_scoring", risk_scoring_node)
    workflow.add_node("release_decision", release_decision_node)
    workflow.add_node("error_handler", error_handler_node)

    # ── Fan-out: START → both parallel agents ────────────────────────────────
    workflow.add_edge(START, "test_analyst")
    workflow.add_edge(START, "performance")

    # ── Fan-in: both parallel agents → risk_scoring ──────────────────────────
    # LangGraph will not execute risk_scoring until BOTH edges are satisfied.
    workflow.add_edge("test_analyst", "risk_scoring")
    workflow.add_edge("performance", "risk_scoring")

    # ── Conditional: risk_scoring → release_decision or error_handler ────────
    workflow.add_conditional_edges(
        "risk_scoring",
        should_proceed_to_decision,
        {
            "release_decision": "release_decision",
            "error_handler": "error_handler",
        },
    )

    # ── Terminal edges ────────────────────────────────────────────────────────
    # route_after_decision always returns "end"; named function kept for
    # future extensibility (retry logic, rollback monitors, etc.)
    workflow.add_conditional_edges(
        "release_decision",
        route_after_decision,
        {"end": END},
    )
    workflow.add_edge("error_handler", END)

    return workflow


def get_guardian_app():
    """Returns the compiled, ready-to-run guardian workflow."""
    workflow = build_guardian_graph()
    app = workflow.compile()
    return app


async def run_guardian(
    build_id: str,
    commit_sha: str,
    branch: str = "main",
    environment: str = "staging",
) -> GuardianState:
    """Execute the full AI Release Guardian pipeline.

    This is the main entry point. Call this from the FastAPI webhook
    handler, the simulation script, or tests.

    Args:
        build_id: CI build identifier (e.g. "build-1847")
        commit_sha: Git commit SHA being evaluated
        branch: Git branch name
        environment: Target deployment environment — affects policy thresholds
                     ("production" is stricter than "staging")

    Returns:
        Final GuardianState with all fields populated.
    """
    logger.info(
        "guardian.start",
        build_id=build_id,
        commit_sha=commit_sha,
        branch=branch,
        environment=environment,
    )

    app = get_guardian_app()
    initial_state = create_initial_state(build_id, commit_sha, branch, environment)

    final_state = await app.ainvoke(initial_state)

    decision = final_state.get("release_decision")
    if decision:
        logger.info(
            "guardian.complete",
            build_id=build_id,
            decision=decision.decision,
            risk_score=decision.risk_score,
            environment=environment,
        )
    else:
        logger.error(
            "guardian.no_decision",
            build_id=build_id,
            message="Guardian analysis failed to produce a decision",
        )

    return final_state


if __name__ == "__main__":

    async def main() -> None:
        state = await run_guardian(
            build_id="build-1847",
            commit_sha="abc12345",
            branch="main",
            environment="production",
        )

        print("\n" + "=" * 60)
        print("GUARDIAN RESULT")
        print("=" * 60)

        if state.get("test_report"):
            print(f"Test:     {state['test_report'].to_summary()}")
        if state.get("perf_report"):
            print(f"Perf:     {state['perf_report'].to_summary()}")
        if state.get("risk_assessment"):
            print(f"Risk:     {state['risk_assessment'].to_summary()}")
        if state.get("release_decision"):
            print(f"Decision: {state['release_decision'].to_summary()}")
        if state.get("errors"):
            print(f"Errors:   {state['errors']}")

    asyncio.run(main())
