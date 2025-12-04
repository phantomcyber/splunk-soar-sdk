from typing import Any

from pydantic import BaseModel, ConfigDict

from soar_sdk.action_results import ActionResult


class ViewContext(BaseModel):
    """Model representing the context dictionary passed to view functions."""

    QS: dict[str, list[str]]
    container: int
    app: int
    no_connection: bool
    google_maps_key: bool | str
    dark_title_logo: str | None = None
    title_logo: str | None = None
    app_name: str | None = None
    results: list[dict[str, Any]] | None = None
    html_content: str | None = None

    model_config = ConfigDict(extra="allow")


class ResultSummary(BaseModel):
    """Summary statistics for an app run."""

    total_objects: int
    total_objects_successful: int


AllAppRuns = list[tuple[ResultSummary, list[ActionResult]]]
