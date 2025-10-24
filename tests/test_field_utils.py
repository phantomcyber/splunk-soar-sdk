from soar_sdk.field_utils import parse_json_schema_extra


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
