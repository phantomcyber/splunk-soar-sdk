from typing import Any, Callable, Type  # noqa: UP035

from pydantic import BaseModel, Field

from soar_sdk.action_results import ActionOutput
from soar_sdk.cli.manifests.serializers import OutputsSerializer, ParamsSerializer
from soar_sdk.params import Params


class ActionMeta(BaseModel):
    """Metadata for an action, to be serialized in the manifest."""

    action: str
    identifier: str
    description: str
    type: str  # contain, correct, generic, investigate or test
    read_only: bool
    versions: str = "EQ(*)"
    verbose: str = ""
    parameters: Type[Params] = Field(default=Params)  # noqa: UP006
    output: Type[ActionOutput] = Field(default=ActionOutput)  # noqa: UP006
    render_as: str | None = None
    view_handler: Callable | None = None
    summary_type: Type[ActionOutput] | None = Field(default=None, exclude=True)  # noqa: UP006
    enable_concurrency_lock: bool = False

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Serializes the action metadata to a dictionary."""
        data = super().model_dump(*args, **kwargs)
        data["parameters"] = ParamsSerializer.serialize_fields_info(self.parameters)
        data["output"] = OutputsSerializer.serialize_datapaths(
            self.parameters, self.output, summary_class=self.summary_type
        )
        if self.view_handler:
            self.render_as = "custom"

        if self.render_as:
            data["render"] = {
                "type": self.render_as,
            }

        if self.view_handler:
            module = self.view_handler.__module__
            module_parts = module.split(".")
            if len(module_parts) > 1:
                relative_module = ".".join(module_parts[1:])
            else:
                relative_module = module
            data["render"]["view"] = f"{relative_module}.{self.view_handler.__name__}"

        # Remove view_handler from the output since in render
        data.pop("view_handler", None)
        data.pop("render_as", None)

        if self.enable_concurrency_lock:
            data["lock"] = {"enabled": True}
        data.pop("enable_concurrency_lock", None)

        return data
