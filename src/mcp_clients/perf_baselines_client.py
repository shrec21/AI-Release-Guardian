"""Performance baselines MCP client."""

from src.mcp_clients.base_client import BaseMCPClient
from src.models.perf_report import BenchmarkResult


class PerfBaselinesMCPClient(BaseMCPClient):
    """Typed client for the Performance Baselines MCP server."""

    def __init__(self, **kwargs) -> None:
        super().__init__(server_name="perf-baselines", **kwargs)

    async def get_current_benchmarks(self, build_id: str) -> list[BenchmarkResult]:
        """Fetch benchmark results for the current build.

        Each raw dict is validated into a ``BenchmarkResult`` model.
        Items that fail validation (e.g. invalid percentile ordering) are
        skipped with a warning.

        Returns:
            List of validated ``BenchmarkResult`` models.
        """
        raw = await self._call_tool(
            "get_current_benchmarks", {"build_id": build_id}
        )
        results: list[BenchmarkResult] = []
        for item in raw:
            try:
                results.append(BenchmarkResult(
                    service=item["service"],
                    endpoint=item.get("endpoint"),
                    latency_p50_ms=item["latency_p50_ms"],
                    latency_p95_ms=item["latency_p95_ms"],
                    latency_p99_ms=item["latency_p99_ms"],
                    throughput_rps=item["throughput_rps"],
                    memory_mb=item["memory_mb"],
                    error_rate=item["error_rate"],
                    sample_count=item.get("sample_count", 0),
                ))
            except Exception as e:
                self.logger.warning(
                    "Failed to parse benchmark result", item=item, error=str(e)
                )
        return results

    async def get_baselines(
        self, service: str, metric: str, window: int = 10
    ) -> list[float]:
        """Fetch historical baseline values for a single metric.

        The server returns a dict keyed by metric name; this method
        extracts just the requested metric's list of values.

        Args:
            service: Service name (e.g. ``"checkout-service"``).
            metric:  Metric key (e.g. ``"latency_p99_ms"``).
            window:  Number of recent deployments to include.

        Returns:
            List of float values from the last ``window`` deployments.
        """
        raw = await self._call_tool(
            "get_baselines", {"service": service, "metric": metric, "window": window}
        )
        if isinstance(raw, dict):
            return raw.get(metric, [])
        if isinstance(raw, list):
            return raw
        return []

    async def get_all_baselines(
        self, service: str, window: int = 10
    ) -> dict[str, list[float]]:
        """Fetch historical baseline values for **all** metrics at once.

        More efficient than calling ``get_baselines`` per-metric when you
        need multiple metrics for a service (single round-trip).

        Returns:
            Dict mapping ``metric_name`` → ``list[float]``.
        """
        raw = await self._call_tool(
            "get_baselines", {"service": service, "window": window}
        )
        return raw if isinstance(raw, dict) else {}

    async def get_slo_definitions(self, service: str) -> list[dict]:
        """Fetch SLO definitions for a service.

        Uses ``safe_call`` — returns an empty list if the SLO registry
        is unavailable, so the agent can still run without SLO checks.

        Returns:
            List of dicts with ``slo_name``, ``service``,
            ``target_description``, ``target_value``.
        """
        result = await self.safe_call(
            "get_slo_definitions", {"service": service}, default=[]
        )
        return result if isinstance(result, list) else []
