import dataclasses
import keyword
import re


@dataclasses.dataclass
class NormalizationResult:
    """
    A named tuple to hold the results of field name normalization.
    """

    original: str
    normalized: str
    modified: bool


def normalize_field_name(field_name: str) -> NormalizationResult:
    """
    Converts a field name to a valid Python identifier
    Args:
        field_name (str): The field name to normalize.
    Returns:
        NormalizationResult: A dataclass containing the original field name,
            the normalized field name, and whether it was modified.
    """
    if not field_name:
        raise ValueError("Field name cannot be an empty string.")

    original = field_name
    if not field_name.isidentifier():
        # Remove invalid characters
        field_name = re.sub(r"[^a-zA-Z0-9_]", "_", field_name)

        # Ensure the first character is a letter or underscore
        if field_name[0].isdigit():
            field_name = f"_{field_name}"

    # Finally, ensure the field name is not a Python keyword
    if keyword.iskeyword(field_name):
        field_name += "_"

    return NormalizationResult(
        original=original, normalized=field_name, modified=original != field_name
    )
