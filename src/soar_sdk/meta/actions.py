import warnings
from typing import Any, Type  # noqa: UP035

from pydantic import BaseModel, ConfigDict, Field, model_validator

from soar_sdk.action_results import ActionOutput
from soar_sdk.cli.manifests.serializers import OutputsSerializer, ParamsSerializer
from soar_sdk.params import Params
from soar_sdk.types import NamedCallable


class ActionLock(BaseModel):
    """Synchronization metadata for an action."""

    model_config = ConfigDict(extra="forbid")

    data_path: str | None = Field(default=None, min_length=1)
    timeout: int | None = Field(default=None, ge=0)


class ActionMeta(BaseModel):
    """Metadata for an action, to be serialized in the manifest."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
    view_handler: NamedCallable | None = None
    summary_type: Type[ActionOutput] | None = Field(default=None, exclude=True)  # noqa: UP006
    lock: ActionLock | None = None
    enable_concurrency_lock: bool = Field(default=False, exclude=True)

    @model_validator(mode="after")
    def normalize_legacy_concurrency_lock(self) -> "ActionMeta":
        """Translate the legacy lock flag while rejecting ambiguous configuration."""
        if getattr(self, "enable_concurrency_lock", False):
            if getattr(self, "lock", None) is not None:
                raise ValueError(
                    "lock and enable_concurrency_lock cannot both be configured"
                )
            warnings.warn(
                "enable_concurrency_lock is deprecated; use lock=ActionLock() instead",
                DeprecationWarning,
                stacklevel=2,
            )
            self.lock = ActionLock()
            self.enable_concurrency_lock = False
        return self

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Serializes the action metadata to a dictionary."""
        data = super().model_dump(*args, **kwargs)
        data.pop("lock", None)
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

        if self.lock is not None:
            data["lock"] = {
                "enabled": True,
                "concurrency": False,
                **self.lock.model_dump(exclude_none=True),
            }

        return data
