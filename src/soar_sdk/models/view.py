from typing import Any, Dict, List, Union, Optional
from pydantic import BaseModel


class ViewContext(BaseModel):
    """Model representing the context dictionary passed to view functions."""

    QS: Dict[str, List[str]]
    container: int
    app: int
    no_connection: bool
    google_maps_key: Union[bool, str]
    dark_title_logo: Optional[str] = None
    title_logo: Optional[str] = None
    app_name: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    html_content: Optional[str] = None

    class Config:
        extra = "allow"


class AppRunMetadata(BaseModel):
    """Model representing metadata for a single app run."""

    action_run_id: Optional[int] = None
    asset_id: Optional[int] = None
    app_run_id: Optional[int] = None
    connector_run_id: Optional[int] = None
    debug_level: Optional[int] = None

    class Config:
        extra = "allow"
