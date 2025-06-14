from typing import Any, Type, Optional, Callable  # noqa: UP035

from pydantic import BaseModel, Field

from soar_sdk.cli.manifests.serializers import ParamsSerializer, OutputsSerializer
from soar_sdk.compat import remove_when_soar_newer_than
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput


class ActionMeta(BaseModel):
    action: str
    identifier: str
    description: str
    type: str  # contain, correct, generic, investigate or test
    read_only: bool
    versions: str = "EQ(*)"
    verbose: str = ""
    parameters: Type[Params] = Field(default=Params)  # noqa: UP006
    output: Type[ActionOutput] = Field(default=ActionOutput)  # noqa: UP006
    view_handler: Optional[Callable] = None

    def dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        data = super().dict(*args, **kwargs)
        data["parameters"] = ParamsSerializer.serialize_fields_info(self.parameters)
        data["output"] = OutputsSerializer.serialize_datapaths(
            self.parameters, self.output
        )

        if self.view_handler:
            remove_when_soar_newer_than("6.4.1")
            # Get the module path and function name for the view
            module = self.view_handler.__module__
            # Convert module path from dot notation to the expected format
            # e.g., "example_app.src.app" -> "src.app"
            module_parts = module.split(".")
            if len(module_parts) > 1:
                # Remove the package name (first part) to get relative module path
                relative_module = ".".join(module_parts[1:])
            else:
                relative_module = module

            data["render"] = {
                "type": "custom",
                "view": f"{relative_module}.{self.view_handler.__name__}",
            }

        # Remove view_handler from the output since in render
        data.pop("view_handler", None)

        return data
