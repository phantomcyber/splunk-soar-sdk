import pytest
from soar_sdk.meta import datatypes


@pytest.mark.parametrize(
    "python_type,expected_datatype",
    (
        (str, "string"),
        (int, "numeric"),
        (float, "numeric"),
        (bool, "boolean"),
    ),
)
def test_as_datatype_valid_types(python_type, expected_datatype):
    """Test as_datatype with valid Python types."""
    assert datatypes.as_datatype(python_type) is expected_datatype


@pytest.mark.parametrize(
    "invalid_type",
    (
        list,
        dict,
        tuple,
        set,
        complex,
        bytes,
        type(None),
    ),
)
def test_as_datatype_invalid_types(invalid_type):
    """Test as_datatype raises TypeError for unsupported types."""
    with pytest.raises(TypeError):
        datatypes.as_datatype(invalid_type)


@pytest.mark.parametrize(
    "datatype,expected_python_type",
    [
        ("string", str),
        ("password", str),
        ("file", str),
        ("numeric", float),
        ("boolean", bool),
    ],
)
def test_to_python_type_valid_datatypes(datatype, expected_python_type):
    """Test to_python_type with valid datatype strings."""
    assert datatypes.to_python_type(datatype) == expected_python_type


@pytest.mark.parametrize(
    "invalid_datatype",
    (
        "integer",
        "text",
        "number",
        "bool",
        "str",
        "list",
        "dict",
        "",
    ),
)
def test_to_python_type_invalid_datatypes(invalid_datatype):
    """Test to_python_type raises TypeError for unsupported datatype strings."""
    with pytest.raises(TypeError, match=f"Unsupported datatype: {invalid_datatype}"):
        datatypes.to_python_type(invalid_datatype)
