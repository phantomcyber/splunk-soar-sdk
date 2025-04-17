def as_datatype(t: type) -> str:
    if t is str:
        return "string"
    elif t in (int, float):
        return "numeric"
    elif t is bool:
        return "boolean"
    raise TypeError(f"Unsupported field type: {t.__name__}")
