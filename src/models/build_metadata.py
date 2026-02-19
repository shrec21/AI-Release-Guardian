"""Build metadata data models.

This module contains Pydantic models for representing build information,
git diffs, and pipeline status in the release guardian system.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class GitDiff(BaseModel):
    """Represents the git diff information for a build.

    Contains details about files changed, lines modified, and which
    services are affected by the changes.
    """

    model_config = ConfigDict(frozen=True)

    files_added: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    files_deleted: list[str] = Field(default_factory=list)
    total_lines_changed: int = Field(ge=0)
    affected_services: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def total_files_changed(self) -> int:
        """Return the total number of files changed (added + modified + deleted)."""
        return len(self.files_added) + len(self.files_modified) + len(self.files_deleted)

    def involves_service(self, service_name: str) -> bool:
        """Check if a service is affected by this diff.

        Args:
            service_name: The name of the service to check.

        Returns:
            True if the service is in affected_services, False otherwise.
        """
        return service_name in self.affected_services


class PipelineStatus(BaseModel):
    """Represents the status of a single pipeline stage.

    Tracks the execution state, timing, and outcome of a CI/CD pipeline stage.
    """

    model_config = ConfigDict(frozen=True)

    stage: str = Field(description="Pipeline stage name, e.g., 'build', 'test', 'deploy'")
    status: Literal["pending", "running", "success", "failure"]
    duration_seconds: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BuildInfo(BaseModel):
    """Represents comprehensive build information.

    Contains all metadata about a CI/CD build including commit info,
    pipeline details, and change information needed for release decisions.
    """

    model_config = ConfigDict(frozen=True)

    build_id: str
    commit_sha: str
    branch: str
    pipeline: str
    trigger: Literal["push", "pr", "manual", "schedule"]
    timestamp: datetime
    files_changed: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    git_diff: GitDiff | None = None
    pipeline_stages: list[PipelineStatus] = Field(default_factory=list)

    def is_main_branch(self) -> bool:
        """Check if the build is on the main branch.

        Returns:
            True if branch is 'main' or 'master', False otherwise.
        """
        return self.branch in ("main", "master")

    def to_summary(self) -> str:
        """Generate a human-readable summary of the build.

        Returns:
            A summary string like "Build build-123 on main (abc1234) - 23 files changed by 2 authors"
        """
        short_sha = self.commit_sha[:7] if len(self.commit_sha) >= 7 else self.commit_sha
        files_count = len(self.files_changed)
        authors_count = len(self.authors)
        return (
            f"Build {self.build_id} on {self.branch} ({short_sha}) - "
            f"{files_count} files changed by {authors_count} authors"
        )
