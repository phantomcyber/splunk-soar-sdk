from typing import Any
from pydantic import BaseModel, root_validator


class BaseAsset(BaseModel):
    """Base class for asset models in SOAR SDK.

    Prevents subclasses from defining fields starting with "_reserved_".
    """

    @root_validator(pre=True)
    def validate_no_reserved_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate that no fields start with '_reserved_'."""
        for field_name in cls.__annotations__:
            if field_name.startswith("_reserved_"):
                raise ValueError(
                    f"Field name '{field_name}' starts with '_reserved_' which is not allowed"
                )
        return values
