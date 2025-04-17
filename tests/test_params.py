import pytest
from pydantic import ValidationError

from tests.stubs import SampleActionParams


def test_models_have_params_validated():
    with pytest.raises(ValidationError):
        SampleActionParams(field1="five")
