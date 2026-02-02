import pytest

from soar_sdk.field_utils import normalize_field_annotation, parse_json_schema_extra


def test_parse_json_schema_extra_with_callable():
    def callable_extra(schema, model):
        return {"foo": "bar"}

    result = parse_json_schema_extra(callable_extra)
    assert result == {}


def test_parse_json_schema_extra_with_dict():
    result = parse_json_schema_extra({"cef_types": ["ip"]})
    assert result == {"cef_types": ["ip"]}


def test_parse_json_schema_extra_with_none():
    result = parse_json_schema_extra(None)
    assert result == {}


def test_normalize_field_annotation_rejects_list_when_not_allowed():
    """Test that list types raise TypeError when allow_list=False."""
    # Test with list[str] when lists are not allowed
    with pytest.raises(TypeError, match="list types are not supported"):
        normalize_field_annotation(
            list[str],
            field_name="test_field",
            context="Parameter",
            allow_list=False,
        )
