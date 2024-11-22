from typing import Type, Any

from pydantic import BaseModel, Field

from soar_sdk.cli.manifests.serializers import ParamsSerializer
from soar_sdk.params import Params


class ActionMeta(BaseModel):
    action: str
    identifier: str
    description: str
    verbose: str
    type: str  # contain, correct, generic, investigate or test
    read_only: bool
    versions: str
    parameters: Type[Params] = Field(default=Params)
    output: list = Field(default_factory=list)

    def dict(self, *args, **kwargs) -> dict[str, Any]:  # type: ignore
        data = super().dict(*args, **kwargs)
        data["parameters"] = ParamsSerializer.serialize_fields_info(self.parameters)
        return data
