"""Base MCP client implementation."""

import abc
import asyncio
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MCPToolError(Exception):
    """Raised when an MCP tool call fails after all retries."""

    def __init__(self, tool_name: str, message: str, attempts: int) -> None:
        self.tool_name = tool_name
        self.attempts = attempts
        super().__init__(
            f"MCP tool '{tool_name}' failed after {attempts} attempts: {message}"
        )


class BaseMCPClient(abc.ABC):
    """Abstract base class for all MCP clients.

    Provides:
    - Tool calling with retry logic and timeout
    - Structured logging for every call
    - Error handling that produces clear, actionable errors
    - Context manager support for connection lifecycle

    Subclasses implement typed methods (like ``get_test_results``) that
    internally call ``self._call_tool()`` with the right tool name and args.
    """

    def __init__(
        self,
        server_name: str,
        max_retries: int = 3,
        timeout_seconds: float = 30.0,
        retry_base_delay: float = 1.0,
    ) -> None:
        self.server_name = server_name
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.retry_base_delay = retry_base_delay
        self._connected = False
        self.logger = structlog.get_logger(__name__).bind(mcp_server=server_name)

    async def connect(self) -> None:
        """Establish connection to the MCP server.

        In live mode this spawns the subprocess. In mock mode this is a no-op.
        """
        self._connected = True
        self.logger.info("MCP client connected")

    async def disconnect(self) -> None:
        """Close the MCP server connection."""
        self._connected = False
        self.logger.info("MCP client disconnected")

    async def __aenter__(self) -> "BaseMCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self.disconnect()
        return False

    async def _call_tool(
        self, tool_name: str, arguments: dict | None = None
    ) -> Any:
        """Call an MCP tool with retry logic, timeout, and structured logging.

        This is the core method that all typed methods delegate to.

        Retry strategy: exponential backoff (1 s, 2 s, 4 s, …)
        - Retries on:     TimeoutError, ConnectionError, OSError, or any
                          other unexpected exception
        - Does NOT retry: ValueError, KeyError — these indicate bad arguments;
                          retrying won't help and would only waste time

        Args:
            tool_name:  The MCP tool to invoke.
            arguments:  Tool arguments as a dict (defaults to empty dict).

        Returns:
            The tool's response (type varies by tool).

        Raises:
            MCPToolError: After all retries are exhausted.
        """
        arguments = arguments or {}
        last_error: BaseException | None = None

        for attempt in range(1, self.max_retries + 1):
            start_time = time.monotonic()
            try:
                self.logger.debug(
                    "Calling MCP tool",
                    tool=tool_name,
                    arguments=arguments,
                    attempt=attempt,
                )

                result = await asyncio.wait_for(
                    self._execute_tool(tool_name, arguments),
                    timeout=self.timeout_seconds,
                )

                duration = time.monotonic() - start_time
                self.logger.info(
                    "MCP tool call succeeded",
                    tool=tool_name,
                    duration_seconds=round(duration, 3),
                    attempt=attempt,
                )
                return result

            except (TimeoutError, asyncio.TimeoutError) as e:
                duration = time.monotonic() - start_time
                last_error = e
                self.logger.warning(
                    "MCP tool call timed out",
                    tool=tool_name,
                    timeout=self.timeout_seconds,
                    attempt=attempt,
                    duration_seconds=round(duration, 3),
                )

            except (ConnectionError, OSError) as e:
                duration = time.monotonic() - start_time
                last_error = e
                self.logger.warning(
                    "MCP tool call connection error",
                    tool=tool_name,
                    error=str(e),
                    attempt=attempt,
                    duration_seconds=round(duration, 3),
                )

            except (ValueError, KeyError) as e:
                # Bad arguments — retrying will never succeed
                raise MCPToolError(tool_name, str(e), attempt) from e

            except Exception as e:
                duration = time.monotonic() - start_time
                last_error = e
                self.logger.warning(
                    "MCP tool call unexpected error",
                    tool=tool_name,
                    error_type=type(e).__name__,
                    error=str(e),
                    attempt=attempt,
                    duration_seconds=round(duration, 3),
                )

            # Exponential backoff before next attempt
            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** (attempt - 1))
                self.logger.debug("Retrying after delay", delay_seconds=delay)
                await asyncio.sleep(delay)

        raise MCPToolError(tool_name, str(last_error), self.max_retries)

    @abc.abstractmethod
    async def _execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Actually execute the tool call. Subclasses implement this.

        - MockMCPClient:       returns fixture data keyed on ``tool_name``
        - LiveMCPClient (TBD): sends the call over stdio to the MCP server process
        """
        ...

    async def safe_call(
        self,
        tool_name: str,
        arguments: dict | None = None,
        default: Any = None,
    ) -> Any:
        """Like ``_call_tool`` but returns a default value instead of raising.

        Use this when a tool failure should not crash the agent — e.g. fetching
        optional data like flaky-test history. The agent can still function
        without that data and the failure is logged as a warning.

        Args:
            tool_name:  The MCP tool to invoke.
            arguments:  Tool arguments as a dict.
            default:    Value to return if the call fails (default: None).

        Returns:
            The tool result on success, or ``default`` on failure.
        """
        try:
            return await self._call_tool(tool_name, arguments)
        except MCPToolError as e:
            self.logger.warning(
                "MCP tool call failed, using default",
                tool=tool_name,
                error=str(e),
                default=str(default),
            )
            return default
