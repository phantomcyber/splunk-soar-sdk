from zoneinfo import ZoneInfo


def as_datatype(t: type) -> str:
    """Convert a Python type to a SOAR data type string."""
    if t is str:
        return "string"
    elif t in (int, float):
        return "numeric"
    elif t is bool:
        return "boolean"
    elif t is ZoneInfo:
        return "timezone"
    raise TypeError(f"Unsupported field type: {t.__name__}")


def to_python_type(datatype: str) -> type:
    """Convert a SOAR data type string to a Python type."""
    datatype = datatype.lower()
    if datatype in ("string", "password", "file"):
        return str
    if datatype == "numeric":
        return float
    if datatype == "boolean":
        return bool
    if datatype == "timezone":
        return ZoneInfo
    raise TypeError(f"Unsupported datatype: {datatype}")
