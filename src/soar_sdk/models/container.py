from typing import Any

from pydantic import BaseModel, ConfigDict


class Container(BaseModel):
    """Represents a container to be created during on_poll.

    This class allows users to specify container properties when yielding from an on_poll function.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    label: str | None = None
    description: str | None = None
    source_data_identifier: str | None = None
    external_id: str | None = None
    severity: str | None = None
    status: str | None = None
    tags: list[str] | str | None = None
    owner_id: int | str | None = None
    sensitivity: str | None = None
    artifacts: list[dict[str, Any]] | None = None
    asset_id: int | None = None
    close_time: str | None = None
    custom_fields: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    due_time: str | None = None
    end_time: str | None = None
    ingest_app_id: int | None = None
    kill_chain: str | None = None
    role_id: int | str | None = None
    run_automation: bool = False
    start_time: str | None = None
    open_time: str | None = None
    tenant_id: int | str | None = None
    container_type: str | None = None
    template_id: int | None = None
    authorized_users: list[int] | None = None
    artifact_count: int | None = None
    container_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the container to a dictionary (needed for save_container)."""
        return self.model_dump(exclude_none=True)
