"""Test logs MCP client."""

from src.mcp_clients.base_client import BaseMCPClient
from src.models.test_report import TestResult


class TestLogsMCPClient(BaseMCPClient):
    """Typed client for the Test Logs MCP server."""

    def __init__(self, **kwargs) -> None:
        super().__init__(server_name="test-logs", **kwargs)

    async def get_test_results(self, build_id: str) -> list[TestResult]:
        """Fetch all test results for a build.

        Each raw dict from the server is validated into a ``TestResult``
        model. Items that fail validation are skipped with a warning so
        one bad record does not discard the entire batch.

        Returns:
            List of validated ``TestResult`` models.
        """
        raw = await self._call_tool("get_test_results", {"build_id": build_id})
        results: list[TestResult] = []
        for item in raw:
            try:
                results.append(TestResult(
                    test_id=item["test_id"],
                    test_name=item["test_name"],
                    suite=item["suite"],
                    status=item["status"],
                    duration_ms=item["duration_ms"],
                    error_message=item.get("error_message"),
                    stack_trace=item.get("stack_trace"),
                ))
            except Exception as e:
                self.logger.warning(
                    "Failed to parse test result", item=item, error=str(e)
                )
        return results

    async def get_coverage_report(self, build_id: str) -> dict:
        """Fetch code coverage data for a build.

        Returns a raw dict with keys:
        ``total_lines``, ``covered_lines``, ``coverage_percentage``,
        ``baseline_coverage``, ``delta``.
        """
        raw = await self._call_tool("get_coverage_report", {"build_id": build_id})
        return raw if isinstance(raw, dict) else {}

    async def get_flaky_history(
        self, test_id: str, window_days: int = 30
    ) -> dict:
        """Fetch flake rate for a specific test over the last N days.

        Uses ``safe_call`` — returns a zero-rate default if the flaky
        database is unavailable, so the agent can still proceed.

        Returns:
            Dict with ``test_id``, ``flake_rate``, ``total_runs``, ``flaky_runs``.
        """
        return await self.safe_call(
            "get_flaky_history",
            {"test_id": test_id, "window_days": window_days},
            default={
                "test_id": test_id,
                "flake_rate": 0.0,
                "total_runs": 0,
                "flaky_runs": 0,
            },
        )

    async def get_test_trends(self, suite: str, limit: int = 20) -> list[dict]:
        """Fetch pass-rate trends for a test suite over recent builds.

        Uses ``safe_call`` — returns an empty list if trend data is
        unavailable without failing the agent.

        Returns:
            List of dicts with ``build`` and ``pass_rate`` keys.
        """
        result = await self.safe_call(
            "get_test_trends",
            {"suite": suite, "limit": limit},
            default=[],
        )
        return result if isinstance(result, list) else []
