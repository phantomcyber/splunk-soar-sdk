from typing import Any


def parse_json_schema_extra(json_schema_extra: Any) -> dict[str, Any]:  # noqa: ANN401
    """Extract json_schema_extra as a dict, handling both dict and callable forms."""
    if callable(json_schema_extra):
        return {}
    return json_schema_extra or {}
