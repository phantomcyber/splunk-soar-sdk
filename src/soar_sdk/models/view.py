from typing import Any, Optional, Union
from pydantic import BaseModel
from soar_sdk.action_results import ActionResult


class ViewContext(BaseModel):
    """Model representing the context dictionary passed to view functions."""

    QS: dict[str, list[str]]
    container: int
    app: int
    no_connection: bool
    google_maps_key: Union[bool, str]
    dark_title_logo: Optional[str] = None
    title_logo: Optional[str] = None
    app_name: Optional[str] = None
    results: Optional[list[dict[str, Any]]] = None
    html_content: Optional[str] = None

    class Config:
        extra = "allow"


class ResultSummary(BaseModel):
    """Summary statistics for an app run."""

    total_objects: int
    total_objects_successful: int


AllAppRuns = list[tuple[ResultSummary, list[ActionResult]]]
