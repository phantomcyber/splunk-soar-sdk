import pytest

from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput


class ExampleInnerData(ActionOutput):
    inner_string: str = OutputField(
        example_values=["example_value_1", "example_value_2"]
    )


class ExampleActionOutput(PermissiveActionOutput):
    under_field: str = OutputField(alias="_under_field")
    stringy_field: str
    list_of_strings: list[str]
    nested_lists: list[list[int]]
    cef_data: str = OutputField(
        cef_types=["ip"], example_values=["192.168.0.1", "1.1.1.1"]
    )
    nested_type: ExampleInnerData
    list_of_types: list[ExampleInnerData]
    optional_field: str | None = None
    optional_inner_field: ExampleInnerData | None = None
    optional_list_of_types: list[ExampleInnerData] | None = None


@pytest.fixture
def valid() -> ExampleActionOutput:
    return ExampleActionOutput(
        under_field="test",
        stringy_field="test2",
        list_of_strings=["a", "b", "c"],
        nested_lists=[[0, 1, 2], []],
        cef_data="192.168.0.1",
        nested_type=ExampleInnerData(inner_string="test_inner"),
        list_of_types=[ExampleInnerData(inner_string="test")],
    )


@pytest.fixture
def invalid() -> ExampleActionOutput:
    return ExampleActionOutput(
        **{
            "_under_field": "test",
            "list_of_strings": ["a", "b", "c"],
            "nested_lists": [[0, 1, 2], []],
            "nested_type": {"inner_string": "test_inner"},
            "list_of_types": [{"inner_string": "test_inner"}, {}],
        }
    )


def test_parse(valid: ExampleActionOutput, invalid: ExampleActionOutput):
    assert valid is not None
    assert invalid is not None


def test_access(invalid: ExampleActionOutput):
    assert invalid.under_field == "test"


def test_nested_access(invalid: ExampleActionOutput):
    assert invalid.nested_type.inner_string == "test_inner"


def test_list_nested_access(invalid: ExampleActionOutput):
    assert invalid.list_of_types[0].inner_string == "test_inner"


def test_missing_attribute_raises(invalid: ExampleActionOutput):
    with pytest.raises(AttributeError):
        _ = invalid.missing_field


def test_access_unknown_field():
    test = ExampleActionOutput(
        **{
            "_under_field": "test",
            "bob": True,
            "list_of_strings": ["a", "b", "c"],
            "nested_lists": [[0, 1, 2], []],
            "nested_type": {"inner_string": "test_inner"},
            "list_of_types": [{"inner_string": "test_inner"}, {}],
        }
    )
    assert test.bob
