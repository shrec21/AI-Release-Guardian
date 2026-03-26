"""Jenkins MCP client."""

from src.mcp_clients.base_client import BaseMCPClient
from src.models.build_metadata import BuildInfo


class JenkinsMCPClient(BaseMCPClient):
    """Typed client for the Jenkins / GitHub Actions MCP server."""

    def __init__(self, **kwargs) -> None:
        super().__init__(server_name="jenkins", **kwargs)

    async def get_build_status(self, build_id: str) -> BuildInfo:
        """Fetch build metadata including files changed, authors, and branch.

        Returns a validated ``BuildInfo`` model.
        """
        raw = await self._call_tool("get_build_status", {"build_id": build_id})
        return BuildInfo.model_validate(raw)

    async def get_build_logs(self, build_id: str) -> str:
        """Fetch raw build log output for a given build."""
        raw = await self._call_tool("get_build_logs", {"build_id": build_id})
        return str(raw)

    async def trigger_stage(
        self, build_id: str, stage: str, action: str
    ) -> bool:
        """Trigger a pipeline action on a specific stage.

        Args:
            build_id: CI build identifier.
            stage:    Pipeline stage name (e.g. ``"deploy"``).
            action:   One of ``"proceed"``, ``"hold"``, or ``"abort"``.

        Returns:
            ``True`` if the action was accepted by Jenkins.
        """
        raw = await self._call_tool(
            "trigger_stage",
            {"build_id": build_id, "stage": stage, "action": action},
        )
        return raw.get("success", False) if isinstance(raw, dict) else bool(raw)

    async def list_recent_builds(
        self, pipeline: str, limit: int = 10
    ) -> list[dict]:
        """List recent builds for a pipeline.

        Returns a list of raw dicts (build_id, status, …). Typed clients
        downstream can further validate these if needed.
        """
        raw = await self._call_tool(
            "list_recent_builds", {"pipeline": pipeline, "limit": limit}
        )
        return raw if isinstance(raw, list) else []
