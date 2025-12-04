import pytest
from pydantic import ValidationError

from soar_sdk.params import MakeRequestParams, Param, Params
from tests.stubs import SampleActionParams


def test_models_have_params_validated():
    with pytest.raises(ValidationError):
        SampleActionParams(field1="five")


def test_sensitive_param_must_be_str():
    class BrokenParams(Params):
        secret: bool = Param(sensitive=True)

    with pytest.raises(TypeError) as e:
        BrokenParams._to_json_schema()

    assert e.match("Sensitive parameter secret must be type str, not bool")


def test_make_request_params_validation():
    """Test that MakeRequestParams validates fields on instantiation in Pydantic v2."""

    class BrokenMakeRequestParams(MakeRequestParams):
        not_allowed: str = Param(description="Not allowed")

    # In Pydantic v2, validation happens on instantiation, not class creation
    with pytest.raises(TypeError) as e:
        BrokenMakeRequestParams(
            http_method="GET", endpoint="/test", not_allowed="value"
        )

    assert (
        str(e.value)
        == "MakeRequestParams subclass 'BrokenMakeRequestParams' can only define these fields: ['body', 'endpoint', 'headers', 'http_method', 'query_parameters', 'timeout', 'verify_ssl']. Invalid fields: ['not_allowed']"
    )


def test_make_request_params_subclass_schema():
    class MakeRequestParamsSubclass(MakeRequestParams):
        query_parameters: str = Param(description="Query parameters for virustotal")

    assert (
        MakeRequestParamsSubclass._to_json_schema()["query_parameters"]["description"]
        == "Query parameters for virustotal"
    )


def test_params_field_without_annotation():
    class BrokenParams(Params):
        field_no_type: str

    BrokenParams.model_fields["field_no_type"].annotation = None

    with pytest.raises(TypeError, match="has no type annotation"):
        BrokenParams._to_json_schema()


def test_param_with_none_values():
    class TestParams(Params):
        field1: str = Param(
            required=None, primary=None, allow_list=None, sensitive=None
        )

    # This should work without errors - None values should skip the if blocks
    schema = TestParams._to_json_schema()
    assert "field1" in schema
