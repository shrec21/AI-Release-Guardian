"""Mock MCP client returning predefined fixture data instead of calling real servers."""

import asyncio
import copy
import datetime
from typing import Any

import structlog

from src.mcp_clients.base_client import BaseMCPClient, MCPToolError


class MockMCPClient(BaseMCPClient):
    """MCP client that returns predefined fixture data instead of calling real servers.

    Usage::

        mock = MockMCPClient("test-logs")
        mock.set_response("get_test_results", {"build-1847": [...]})
        result = await mock._call_tool("get_test_results", {"build_id": "build-1847"})

    Supports:
    - Static responses per tool name
    - Argument-keyed responses (different data for different argument values)
    - Simulated failures (raises any configured exception)
    - Simulated latency (configurable delay in milliseconds)
    - Call history tracking for assertions in tests
    """

    def __init__(self, server_name: str, latency_ms: float = 50.0) -> None:
        # max_retries=1 so tests don't sit through exponential backoff
        super().__init__(server_name=server_name, max_retries=1, timeout_seconds=5.0)
        self._responses: dict[str, Any] = {}
        # tool_name → {"field:value": response}
        self._keyed_responses: dict[str, dict[str, Any]] = {}
        self._failures: dict[str, Exception] = {}
        self._call_history: list[dict] = []
        self._latency_ms = latency_ms
        self.logger = structlog.get_logger(__name__).bind(
            mcp_server=server_name, mode="mock"
        )

    # ── Response configuration ────────────────────────────────────────────────

    def set_response(self, tool_name: str, response: Any) -> None:
        """Set a static response for a tool, returned regardless of arguments."""
        self._responses[tool_name] = response

    def set_keyed_response(
        self,
        tool_name: str,
        key_field: str,
        key_value: str,
        response: Any,
    ) -> None:
        """Set a response for a specific argument value.

        Example::

            mock.set_keyed_response("get_test_results", "build_id", "build-1847", data_a)
            mock.set_keyed_response("get_test_results", "build_id", "build-9999", data_b)

        When ``get_test_results`` is called, the value of ``arguments["build_id"]``
        is used to pick the right response.
        """
        if tool_name not in self._keyed_responses:
            self._keyed_responses[tool_name] = {}
        compound_key = f"{key_field}:{key_value}"
        self._keyed_responses[tool_name][compound_key] = response

    def set_failure(self, tool_name: str, error: Exception) -> None:
        """Make a tool raise an exception when called. Useful for testing error paths."""
        self._failures[tool_name] = error

    def clear_failure(self, tool_name: str) -> None:
        """Remove a previously configured failure."""
        self._failures.pop(tool_name, None)

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def call_history(self) -> list[dict]:
        """All tool calls made so far: ``[{tool, arguments, timestamp}, ...]``."""
        return self._call_history.copy()

    def get_calls_for(self, tool_name: str) -> list[dict]:
        """Return only calls made to a specific tool."""
        return [c for c in self._call_history if c["tool"] == tool_name]

    def reset(self) -> None:
        """Clear all responses, failures, and call history."""
        self._responses.clear()
        self._keyed_responses.clear()
        self._failures.clear()
        self._call_history.clear()

    # ── Core execution ────────────────────────────────────────────────────────

    async def _execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Return mock data based on ``tool_name`` and ``arguments``.

        Resolution order:

        1. Configured failure → raise exception
        2. Keyed response matching ``arguments[key_field] == key_value`` → return
        3. Static response → return
        4. Nothing configured → raise ``MCPToolError``
        """
        # Record the call
        self._call_history.append({
            "tool": tool_name,
            "arguments": copy.deepcopy(arguments),
            "timestamp": datetime.datetime.now(datetime.timezone.utc),
        })

        # Simulate network latency
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000)

        # 1. Configured failure
        if tool_name in self._failures:
            raise self._failures[tool_name]

        # 2. Keyed responses (argument-specific, more precise)
        if tool_name in self._keyed_responses:
            for compound_key, response in self._keyed_responses[tool_name].items():
                key_field, key_value = compound_key.split(":", 1)
                if arguments.get(key_field) == key_value:
                    self.logger.debug(
                        "Mock returning keyed response",
                        tool=tool_name,
                        key=compound_key,
                    )
                    return copy.deepcopy(response)

        # 3. Static response
        if tool_name in self._responses:
            self.logger.debug("Mock returning static response", tool=tool_name)
            return copy.deepcopy(self._responses[tool_name])

        # 4. Nothing configured
        raise MCPToolError(
            tool_name,
            f"No mock response configured for tool '{tool_name}' "
            f"on server '{self.server_name}'",
            1,
        )


# ── Pre-configured fixture factory ────────────────────────────────────────────

def create_preconfigured_mock(server_name: str) -> MockMCPClient:
    """Create a MockMCPClient pre-loaded with realistic fixture data.

    All fixtures match the **build-1847** scenario:
    - 430/435 tests pass; 1 new bug, 1 flaky, 1 infra error
    - Critical P99 latency regression on checkout-service (318 ms vs 189 ms baseline)
    - Medium blast radius including critical payment-service

    Args:
        server_name: One of ``"test-logs"``, ``"perf-baselines"``,
                     ``"jenkins"``, ``"deploy-history"``.

    Returns:
        A fully configured ``MockMCPClient`` ready to use.
    """
    mock = MockMCPClient(server_name)

    if server_name == "test-logs":
        # 430 passing tests
        mock.set_response("get_test_results", [
            {
                "test_id": f"test_{i}",
                "test_name": f"test_case_{i}",
                "suite": "CoreSuite",
                "status": "passed",
                "duration_ms": 45.0 + (i % 20),
                "error_message": None,
                "stack_trace": None,
            }
            for i in range(430)
        ] + [
            {
                "test_id": "test_payment_charge",
                "test_name": "test_payment_processor_charge",
                "suite": "PaymentSuite",
                "status": "failed",
                "duration_ms": 1200.0,
                "error_message": (
                    "NullPointerException: processor.charge() received null paymentMethod"
                ),
                "stack_trace": (
                    "at PaymentProcessor.charge(processor.py:42)\n"
                    "at CheckoutService.complete(checkout.py:118)"
                ),
            },
            {
                "test_id": "test_session_timeout",
                "test_name": "test_user_session_timeout",
                "suite": "AuthSuite",
                "status": "failed",
                "duration_ms": 5023.0,
                "error_message": (
                    "AssertionError: Expected session to expire after 30s, but was still active"
                ),
                "stack_trace": "at test_user_session_timeout(test_auth.py:87)",
            },
            {
                "test_id": "test_external_api",
                "test_name": "test_external_api_integration",
                "suite": "IntegrationSuite",
                "status": "error",
                "duration_ms": 30000.0,
                "error_message": (
                    "ConnectionRefusedError: Cannot connect to staging-api.internal:8080"
                ),
                "stack_trace": (
                    "at ExternalAPIClient.call(api_client.py:23)\n"
                    "at test_external_api_integration(test_integration.py:45)"
                ),
            },
            {
                "test_id": "test_skip_1",
                "test_name": "test_deprecated_feature",
                "suite": "LegacySuite",
                "status": "skipped",
                "duration_ms": 0,
                "error_message": "Deprecated",
                "stack_trace": None,
            },
            {
                "test_id": "test_skip_2",
                "test_name": "test_feature_flag_disabled",
                "suite": "FeatureSuite",
                "status": "skipped",
                "duration_ms": 0,
                "error_message": "Feature flag off",
                "stack_trace": None,
            },
        ])

        mock.set_response("get_coverage_report", {
            "total_lines": 15420,
            "covered_lines": 13452,
            "coverage_percentage": 87.3,
            "baseline_coverage": 88.5,
            "delta": -1.2,
        })

        # Flaky history — keyed by test_id
        mock.set_keyed_response(
            "get_flaky_history", "test_id", "test_payment_charge",
            {"test_id": "test_payment_charge", "flake_rate": 0.02,
             "total_runs": 100, "flaky_runs": 2},
        )
        mock.set_keyed_response(
            "get_flaky_history", "test_id", "test_session_timeout",
            {"test_id": "test_session_timeout", "flake_rate": 0.45,
             "total_runs": 100, "flaky_runs": 45},
        )
        mock.set_keyed_response(
            "get_flaky_history", "test_id", "test_external_api",
            {"test_id": "test_external_api", "flake_rate": 0.08,
             "total_runs": 100, "flaky_runs": 8},
        )

        mock.set_response("get_test_trends", [
            {"build": f"build-{1840 + i}", "pass_rate": 0.98 - (i * 0.002)}
            for i in range(10)
        ])

    elif server_name == "perf-baselines":
        mock.set_response("get_current_benchmarks", [
            {
                "service": "checkout-service",
                "endpoint": "/api/v1/checkout",
                "latency_p50_ms": 48.0,
                "latency_p95_ms": 142.0,
                "latency_p99_ms": 318.0,
                "throughput_rps": 1150.0,
                "memory_mb": 524.0,
                "error_rate": 0.003,
                "sample_count": 1000,
            }
        ])

        mock.set_response("get_baselines", {
            "latency_p50_ms":  [43, 45, 42, 44, 41, 46, 43, 44, 42, 45],
            "latency_p95_ms":  [125, 130, 128, 132, 126, 129, 131, 127, 133, 128],
            "latency_p99_ms":  [185, 192, 188, 195, 190, 187, 193, 189, 191, 186],
            "throughput_rps":  [1280, 1310, 1265, 1290, 1300, 1275, 1295, 1285, 1270, 1305],
            "memory_mb":       [498, 505, 512, 495, 502, 509, 501, 497, 506, 503],
            "error_rate":      [0.002, 0.003, 0.001, 0.002, 0.003,
                                0.002, 0.001, 0.002, 0.003, 0.002],
        })

        mock.set_response("get_slo_definitions", [
            {
                "slo_name": "checkout-service P99 latency",
                "service": "checkout-service",
                "target_description": "P99 < 250ms",
                "target_value": 250.0,
            },
            {
                "slo_name": "checkout-service error rate",
                "service": "checkout-service",
                "target_description": "Error rate < 1%",
                "target_value": 0.01,
            },
        ])

    elif server_name == "jenkins":
        mock.set_response("get_build_status", {
            "build_id": "build-1847",
            "commit_sha": "abc12345",
            "branch": "main",
            "pipeline": "checkout-service-ci",
            "trigger": "push",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "files_changed": [
                "src/payment/processor.py",
                "src/payment/models.py",
                "src/payment/tests/test_processor.py",
                "src/checkout/service.py",
                "src/checkout/handlers.py",
                "src/api/routes/checkout.py",
                "src/api/routes/payment.py",
                "src/common/utils.py",
                "src/common/exceptions.py",
                "config/payment-gateway.yaml",
                "docs/api-reference.md",
                "docs/changelog.md",
                "scripts/migrate_payment_tables.sql",
                "src/notification/email.py",
                "src/notification/templates/receipt.html",
                "tests/integration/test_checkout_flow.py",
                "tests/integration/test_payment_flow.py",
                "src/analytics/events.py",
                "src/analytics/trackers.py",
                "requirements.txt",
                "pyproject.toml",
                "docker-compose.yml",
                ".github/workflows/ci.yml",
            ],
            "authors": ["shreyas", "alex"],
        })

        mock.set_response(
            "get_build_logs",
            "... [BUILD LOG] Running tests... 435 tests executed in 124s ...",
        )
        mock.set_response("trigger_stage", {
            "success": True,
            "message": "Stage action applied",
        })
        mock.set_response("list_recent_builds", [
            {
                "build_id": f"build-{1847 - i}",
                "status": "success" if i != 3 else "failure",
            }
            for i in range(10)
        ])

    elif server_name == "deploy-history":
        now = datetime.datetime.now(datetime.timezone.utc)
        mock.set_response("get_deployment_history", [
            {
                "deploy_id": f"deploy-{i}",
                "service": "checkout-service",
                "status": "success" if i not in (5, 12) else "rolled_back",
                "timestamp": (now - datetime.timedelta(days=i)).isoformat(),
                "risk_score": 15 + (i * 3),
                "duration_minutes": 8.5 + (i * 0.5),
            }
            for i in range(20)
        ])

        mock.set_response("get_rollback_rate", {
            "service": "checkout-service",
            "window_days": 90,
            "total_deploys": 20,
            "rollbacks": 2,
            "rollback_rate": 0.10,
        })

        mock.set_response("get_incident_correlation", [])

        mock.set_response("get_change_patterns", [
            {"diff_similarity": 0.72, "outcome": "success",     "risk_score": 28},
            {"diff_similarity": 0.65, "outcome": "success",     "risk_score": 22},
            {"diff_similarity": 0.58, "outcome": "rolled_back", "risk_score": 45},
        ])

        mock.set_response("log_decision", {
            "success": True,
            "decision_id": "audit-uuid-12345",
        })

    return mock
