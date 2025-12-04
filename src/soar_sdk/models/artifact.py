from typing import Any

from pydantic import BaseModel, ConfigDict


class Artifact(BaseModel):
    """Represents an artifact to be created during on_poll.

    This class allows users to create artifacts when yielding from an 'on poll' action.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    label: str | None = None
    description: str | None = None
    type: str | None = None
    severity: str | None = None
    source_data_identifier: str | None = None
    container_id: int | None = None
    data: dict[str, Any] | None = None
    run_automation: bool = False
    owner_id: int | str | None = None
    cef: dict[str, Any] | None = None
    cef_types: dict[str, list[str]] | None = None
    ingest_app_id: int | str | None = None
    tags: list[str] | str | None = None
    start_time: str | None = None
    end_time: str | None = None
    kill_chain: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the artifact to a dictionary (needed for save_artifact)."""
        return self.model_dump(exclude_none=True)
