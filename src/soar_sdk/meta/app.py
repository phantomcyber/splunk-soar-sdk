from pydantic import BaseModel, Field
from typing import Optional

from soar_sdk.asset import AssetFieldSpecification
from soar_sdk.compat import PythonVersion

from .actions import ActionMeta
from .dependencies import DependencyList
from .webhooks import WebhookMeta


class AppContributor(BaseModel):
    name: str


class AppMeta(BaseModel):
    name: str = ""
    description: str
    appid: str = "1e1618e7-2f70-4fc0-916a-f96facc2d2e4"  # placeholder value to pass inital validation
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
    python_version: list[PythonVersion] = Field(default_factory=PythonVersion.all)
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

    def to_json_manifest(self) -> dict:
        """
        Converts the AppMeta instance to a JSON-compatible dictionary.
        """
        return self.dict(exclude_none=True)
