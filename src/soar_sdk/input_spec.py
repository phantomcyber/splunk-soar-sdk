import random
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def id_factory() -> int:
    """Generate a random database ID."""
    return random.randint(1, 1000000)  # noqa: S311


class IngestConfig(BaseModel):
    """Configuration for app ingest functionality."""

    container_label: str


class AppConfig(BaseModel):
    """Configuration for the SOAR app."""

    app_version: str
    directory: str
    ingest: IngestConfig | None = None
    main_module: str
    # TODO: The platform should deprecate this unused field
    appname: Literal["-"] = "-"

    # NOTE: Inputs will intermix the keys of the asset config with the keys here
    model_config = ConfigDict(extra="allow")

    def get_asset_config(self) -> dict[str, Any]:
        """Get the asset configuration from the app config."""
        # In Pydantic v2 extra fields are stored in __pydantic_extra__
        return dict(self.__pydantic_extra__) if self.__pydantic_extra__ else {}


class EnvironmentVariable(BaseModel):
    """Model for environment variable configuration."""

    # TODO: How does the platform send secret environment variables?
    type: str
    value: str


class ParameterContext(BaseModel):
    """Context information for action parameters."""

    artifact_id: int = Field(default_factory=id_factory)
    guid: str = Field(default_factory=lambda: str(uuid4()))
    # TODO: How to get an action which populates this field?
    parent_action_run: list = []


class ActionParameter(BaseModel):
    """Parameter passed to an action.

    This can include any key/value pairs as parameters, with a special
    'context' field containing metadata.
    """

    # Removed to prevent from appearing in parameters unless explicitly provided as an extra field
    # Was causing issues with the platform during check on context (which was None from here)
    # context: Optional[ParameterContext] = None # noqa: ERA001

    # Additional keys are action-specific and not predictable here.
    model_config = ConfigDict(extra="allow")


class SoarAuth(BaseModel):
    """Information to help authenticate with SOAR."""

    phantom_url: str
    username: str
    password: str

    @field_validator("phantom_url")
    @classmethod
    def validate_phantom_url(cls, value: str) -> str:
        """Ensure the URL starts with http:// or https://."""
        return (
            f"https://{value}"
            if not value.startswith(("http://", "https://"))
            else value
        )


class InputSpecification(BaseModel):
    """Input specification for SOAR app _handle_action() method.

    Example JSON from the platform:
    {
        "action": "test_connectivity",
        "action_run_id": 123456,
        "app_config": null,
        "asset_id": "10",
        "config": {
            "app_version": "1.0.0",
            "appname": "Example App",
            "base_url": "https://soar.example.com",
            "directory": "/opt/phantom/apps/example_app",
            "ingest": {
                "container_label": "events"
            },
            "main_module": "example_connector.py"
        },
        "connector_run_id": 78910,
        "container_id": 12345,
        "debug_level": 3,
        "dec_key": "*****",
        "environment_variables": {
            "HTTPS_PROXY": {
                "type": "string",
                "value": "https://proxy.example.com"
            },
            "NO_PROXY": {
                "type": "string",
                "value": "127.0.0.1,localhost"
            }
        },
        "identifier": "test_connectivity",
        "parameters": [
            {
                "source": "input",
                "dest": "output",
                "context": {
                    "artifact_id": 42,
                    "guid": "artifact_guid_123",
                    "parent_action_run": []
                }
            }
        ],
        "user_session_token": "session_token_value"
    }
    """

    action: str | None = None
    action_run_id: int = Field(default_factory=id_factory)
    app_config: Any | None = None
    asset_id: str = Field(default_factory=lambda: str(id_factory()))
    config: AppConfig
    connector_run_id: int = Field(default_factory=id_factory)
    container_id: int = Field(default_factory=id_factory)
    debug_level: int = 3
    dec_key: str = Field(default_factory=lambda: str(id_factory()))
    environment_variables: dict[str, EnvironmentVariable] = Field(default_factory=dict)
    identifier: str
    parameters: list[ActionParameter] = Field(default_factory=list)
    user_session_token: str = ""
    soar_auth: SoarAuth | None = None
