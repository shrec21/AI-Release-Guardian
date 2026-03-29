"""Deploy history MCP client."""

from src.mcp_clients.base_client import BaseMCPClient


class DeployHistoryMCPClient(BaseMCPClient):
    """Typed client for the Deployment History MCP server."""

    def __init__(self, **kwargs) -> None:
        super().__init__(server_name="deploy-history", **kwargs)

    async def get_deployment_history(
        self, service: str, limit: int = 20
    ) -> list[dict]:
        """Fetch recent deployment history for a service.

        Returns:
            List of dicts with ``deploy_id``, ``service``, ``status``,
            ``timestamp``, ``risk_score``, and ``duration_minutes``.
        """
        raw = await self._call_tool(
            "get_deployment_history", {"service": service, "limit": limit}
        )
        return raw if isinstance(raw, list) else []

    async def get_rollback_rate(
        self, service: str, window_days: int = 90
    ) -> dict:
        """Fetch rollback statistics for a service over a time window.

        Returns:
            Dict with ``service``, ``total_deploys``, ``rollbacks``,
            and ``rollback_rate`` (fraction 0–1).
            Falls back to a zero-rate dict on failure.
        """
        raw = await self._call_tool(
            "get_rollback_rate", {"service": service, "window_days": window_days}
        )
        return raw if isinstance(raw, dict) else {
            "rollback_rate": 0.0,
            "total_deploys": 0,
            "rollbacks": 0,
        }

    async def get_incident_correlation(self, deploy_id: str) -> list[dict]:
        """Check whether a deployment was correlated with any incidents.

        Uses ``safe_call`` — returns an empty list if the incident store
        is unavailable.

        Returns:
            List of correlated incident dicts, or ``[]`` if none found.
        """
        result = await self.safe_call(
            "get_incident_correlation", {"deploy_id": deploy_id}, default=[]
        )
        return result if isinstance(result, list) else []

    async def get_change_patterns(self, diff_hash: str) -> list[dict]:
        """Find historically similar changes and their outcomes.

        Uses ``safe_call`` — historical pattern data is optional; agents
        can still make decisions without it.

        Returns:
            List of dicts with ``diff_similarity``, ``outcome``, and
            ``risk_score``.
        """
        result = await self.safe_call(
            "get_change_patterns", {"diff_hash": diff_hash}, default=[]
        )
        return result if isinstance(result, list) else []

    async def log_decision(
        self, build_id: str, decision: str, audit_data: dict
    ) -> bool:
        """Record a release decision in the deployment history store.

        Args:
            build_id:   CI build identifier.
            decision:   One of ``"APPROVE"``, ``"REQUEST_REVIEW"``, ``"BLOCK"``.
            audit_data: Full audit payload to persist.

        Returns:
            ``True`` if the record was successfully stored.
        """
        raw = await self._call_tool(
            "log_decision",
            {"build_id": build_id, "decision": decision, "audit_data": audit_data},
        )
        return raw.get("success", False) if isinstance(raw, dict) else bool(raw)
