"""Factory functions for creating MCP client sets."""

from typing import Any

import structlog

from src.config import get_settings
from src.mcp_clients.base_client import BaseMCPClient
from src.mcp_clients.deploy_history_client import DeployHistoryMCPClient
from src.mcp_clients.jenkins_client import JenkinsMCPClient
from src.mcp_clients.mock_client import MockMCPClient, create_preconfigured_mock
from src.mcp_clients.perf_baselines_client import PerfBaselinesMCPClient
from src.mcp_clients.test_logs_client import TestLogsMCPClient

logger = structlog.get_logger(__name__)


def _typed_mock(TypedClass: type, server_name: str) -> BaseMCPClient:
    """Return a typed client whose transport is backed by a MockMCPClient.

    The returned object has:
    - All typed methods from ``TypedClass`` (e.g. ``get_test_results``)
    - ``call_history`` / ``get_calls_for`` from the underlying mock
    - ``_execute_tool`` delegated to the pre-configured fixture data
    """
    mock_backend: MockMCPClient = create_preconfigured_mock(server_name)

    class _Concrete(TypedClass):  # type: ignore[valid-type]
        async def _execute_tool(self, tool_name: str, arguments: dict) -> Any:
            return await mock_backend._execute_tool(tool_name, arguments)

        @property
        def call_history(self) -> list[dict]:
            return mock_backend.call_history

        def get_calls_for(self, tool_name: str) -> list[dict]:
            return mock_backend.get_calls_for(tool_name)

        def reset(self) -> None:
            mock_backend.reset()

    return _Concrete()


def get_mock_clients() -> dict[str, BaseMCPClient]:
    """Create all four typed MCP clients backed by pre-configured mock data.

    Returns typed clients (``JenkinsMCPClient``, ``TestLogsMCPClient``, etc.)
    whose transport delegates to fixture data — so all typed methods work, and
    ``call_history`` is tracked per-client for verification.

    Use for development, testing, and demos. No real servers required.
    """
    logger.info("Creating mock MCP clients")
    return {
        "jenkins":       _typed_mock(JenkinsMCPClient,       "jenkins"),
        "test_logs":     _typed_mock(TestLogsMCPClient,      "test-logs"),
        "perf_baselines": _typed_mock(PerfBaselinesMCPClient, "perf-baselines"),
        "deploy_history": _typed_mock(DeployHistoryMCPClient, "deploy-history"),
    }


def get_live_clients() -> dict[str, BaseMCPClient]:
    """Create all four typed MCP clients configured to call real servers.

    Server commands and arguments are read from ``Settings`` (via
    ``GUARDIAN_MCP_*`` environment variables / ``.env`` file).
    Use in production.
    """
    settings = get_settings()
    logger.info(
        "Creating live MCP clients",
        jenkins_cmd=settings.mcp_jenkins_command,
        test_logs_cmd=settings.mcp_test_logs_command,
        perf_baselines_cmd=settings.mcp_perf_baselines_command,
        deploy_history_cmd=settings.mcp_deploy_history_command,
    )
    return {
        "jenkins": JenkinsMCPClient(),
        "test_logs": TestLogsMCPClient(),
        "perf_baselines": PerfBaselinesMCPClient(),
        "deploy_history": DeployHistoryMCPClient(),
    }


def get_mcp_clients(use_mocks: bool = True) -> dict[str, BaseMCPClient]:
    """Factory function for the full set of MCP clients.

    Args:
        use_mocks: When ``True`` (default), returns mock clients pre-loaded
                   with the build-1847 fixture data — safe for development
                   and CI. When ``False``, returns live typed clients that
                   connect to real MCP server processes.

    Returns:
        Dict mapping client name to client instance::

            {
                "jenkins":       JenkinsMCPClient  | MockMCPClient,
                "test_logs":     TestLogsMCPClient | MockMCPClient,
                "perf_baselines": PerfBaselinesMCPClient | MockMCPClient,
                "deploy_history": DeployHistoryMCPClient | MockMCPClient,
            }
    """
    if use_mocks:
        return get_mock_clients()
    return get_live_clients()
