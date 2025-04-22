from typing import Any, Type  # noqa: UP035

from pydantic import BaseModel, Field

from soar_sdk.cli.manifests.serializers import ParamsSerializer, OutputsSerializer
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput


class ActionMeta(BaseModel):
    action: str
    identifier: str
    description: str
    verbose: str
    type: str  # contain, correct, generic, investigate or test
    read_only: bool
    versions: str
    parameters: Type[Params] = Field(default=Params)  # noqa: UP006
    output: Type[ActionOutput] = Field(default=ActionOutput)  # noqa: UP006

    def dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        data = super().dict(*args, **kwargs)
        data["parameters"] = ParamsSerializer.serialize_fields_info(self.parameters)
        data["output"] = OutputsSerializer.serialize_datapaths(
            self.parameters, self.output
        )
        return data
