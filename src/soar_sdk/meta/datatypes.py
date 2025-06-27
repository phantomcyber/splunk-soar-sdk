def as_datatype(t: type) -> str:
    if t is str:
        return "string"
    elif t in (int, float):
        return "numeric"
    elif t is bool:
        return "boolean"
    raise TypeError(f"Unsupported field type: {t.__name__}")


def to_python_type(datatype: str) -> type:
    datatype = datatype.lower()
    if datatype in ("string", "password", "file"):
        return str
    if datatype == "numeric":
        return float
    if datatype == "boolean":
        return bool
    raise TypeError(f"Unsupported datatype: {datatype}")
