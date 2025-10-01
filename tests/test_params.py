import pytest
from pydantic import ValidationError

from soar_sdk.params import Param, Params, MakeRequestParams

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
    with pytest.raises(TypeError) as e:

        class BrokenMakeRequestParams(MakeRequestParams):
            not_allowed: str = Param(description="Not allowed")

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
