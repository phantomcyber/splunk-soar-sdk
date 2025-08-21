import pytest
from pydantic import ValidationError

from soar_sdk.params import Param, Params

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
