from pydantic import BaseModel, Field, validator
from typing import Optional, Union

from soar_sdk.asset import AssetFieldSpecification
from soar_sdk.compat import PythonVersion

from .actions import ActionMeta
from .dependencies import DependencyList
from .webhooks import WebhookMeta


class AppContributor(BaseModel):
    """Canonical format for the 'contributors' object in the app manifest."""

    name: str


class AppMeta(BaseModel):
    """Model for an app's core metadata, which makes up much of its manifest."""

    name: str = ""
    description: str
    appid: str = "1e1618e7-2f70-4fc0-916a-f96facc2d2e4"  # placeholder value to pass initial validation
    type: str = ""
    product_vendor: str = ""
    app_version: str
    license: str
    min_phantom_version: str = ""
    package_name: str
    project_name: str = Field(exclude=True)
    main_module: str = "src/app.py:app"  # TODO: Some validation would be nice
    logo: str = ""
    logo_dark: str = ""
    product_name: str = ""
    python_version: str = Field(default_factory=PythonVersion.all_csv)
    product_version_regex: str = ".*"
    publisher: str = ""
    utctime_updated: str = ""
    fips_compliant: bool = False
    contributors: list[AppContributor] = Field(default_factory=list)

    configuration: dict[str, AssetFieldSpecification] = Field(default_factory=dict)
    actions: list[ActionMeta] = Field(default_factory=list)

    pip39_dependencies: DependencyList = Field(default_factory=DependencyList)
    pip313_dependencies: DependencyList = Field(default_factory=DependencyList)

    webhook: Optional[WebhookMeta]

    @validator("python_version", pre=True)
    def convert_python_version_to_csv(cls, v: Union[list, str]) -> str:
        """Converts python_version to a comma-separated string if it's a list and validates versions."""
        if isinstance(v, list):
            # Validate each version in the list and convert to CSV
            validated_versions = [PythonVersion.from_str(str(version)) for version in v]
            return PythonVersion.to_csv(validated_versions)
        elif isinstance(v, str):
            # Validate the CSV string by parsing it and convert back to CSV
            validated_versions = PythonVersion.from_csv(v)
            return PythonVersion.to_csv(validated_versions)
        raise ValueError(
            f"Invalid python_version type must be a list or a comma-separated string: {v}"
        )

    def to_json_manifest(self) -> dict:
        """Converts the AppMeta instance to a JSON-compatible dictionary."""
        return self.dict(exclude_none=True)
