"""MCP clients module.

Re-exports all client classes so callers import from one place:

    from src.mcp_clients import TestLogsMCPClient, create_preconfigured_mock
"""

from src.mcp_clients.base_client import BaseMCPClient, MCPToolError
from src.mcp_clients.deploy_history_client import DeployHistoryMCPClient
from src.mcp_clients.jenkins_client import JenkinsMCPClient
from src.mcp_clients.mock_client import MockMCPClient, create_preconfigured_mock
from src.mcp_clients.perf_baselines_client import PerfBaselinesMCPClient
from src.mcp_clients.test_logs_client import TestLogsMCPClient

__all__ = [
    # base
    "BaseMCPClient",
    "MCPToolError",
    # mock
    "MockMCPClient",
    "create_preconfigured_mock",
    # typed clients
    "JenkinsMCPClient",
    "TestLogsMCPClient",
    "PerfBaselinesMCPClient",
    "DeployHistoryMCPClient",
]
