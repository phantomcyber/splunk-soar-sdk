from pydantic import BaseModel
from typing import Optional, Any, Union


class Container(BaseModel):
    """
    Represents a container to be created during on_poll.

    This class allows users to specify container properties when yielding from an on_poll function.
    """

    class Config:
        extra = "forbid"

    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    source_data_identifier: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[Union[list[str], str]] = None
    owner_id: Optional[Union[int, str]] = None
    sensitivity: Optional[str] = None
    artifacts: Optional[list[dict[str, Any]]] = None
    asset_id: Optional[int] = None
    close_time: Optional[str] = None
    custom_fields: Optional[dict[str, Any]] = None
    data: Optional[dict[str, Any]] = None
    due_time: Optional[str] = None
    end_time: Optional[str] = None
    ingest_app_id: Optional[int] = None
    kill_chain: Optional[str] = None
    role_id: Optional[Union[int, str]] = None
    run_automation: bool = False
    start_time: Optional[str] = None
    open_time: Optional[str] = None
    tenant_id: Optional[Union[int, str]] = None
    container_type: Optional[str] = None
    template_id: Optional[int] = None
    authorized_users: Optional[list[int]] = None
    artifact_count: Optional[int] = None
    container_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the container to a dictionary (needed for save_container).
        """
        return self.dict(exclude_none=True)
