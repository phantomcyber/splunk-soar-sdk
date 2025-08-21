from typing import Optional, Any, Union
from pydantic import BaseModel


class Artifact(BaseModel):
    """
    Represents an artifact to be created during on_poll.

    This class allows users to create and configure artifacts when yielding from an on_poll function.
    """

    class Config:
        extra = "forbid"

    name: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    severity: Optional[str] = None
    source_data_identifier: Optional[str] = None
    container_id: Optional[int] = None
    data: Optional[dict[str, Any]] = None
    run_automation: bool = False
    owner_id: Optional[Union[int, str]] = None
    cef: Optional[dict[str, Any]] = None
    cef_types: Optional[dict[str, list[str]]] = None
    ingest_app_id: Optional[Union[int, str]] = None
    tags: Optional[Union[list[str], str]] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    kill_chain: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the artifact to a dictionary (needed for save_artifact).
        """
        return self.dict(exclude_none=True)
