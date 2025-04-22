from pydantic import BaseModel, Field

from .actions import ActionMeta
from .dependencies import DependencyList


class AppMeta(BaseModel):
    name: str
    description: str
    appid: str
    type: str
    product_vendor: str
    app_version: str
    license: str
    min_phantom_version: str
    package_name: str
    main_module: str = "src/app.py:app"  # TODO: Some validation would be nice
    logo: str = ""
    logo_dark: str = ""
    product_name: str = ""
    python_version: str = "3"
    product_version_regex: str = ".*"
    publisher: str = ""
    utctime_updated: str = ""
    app_wizard_version: str = ""
    fips_compliant: bool = False

    configuration: dict = Field(default_factory=dict)
    actions: list[ActionMeta] = Field(default_factory=list)

    pip39_dependencies: DependencyList = Field(default_factory=DependencyList)
    pip313_dependencies: DependencyList = Field(default_factory=DependencyList)
