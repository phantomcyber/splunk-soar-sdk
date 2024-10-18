import pytest

from soar_sdk.params import Param


def test_param_required_fields():
    param = Param(0, "some description")

    assert param.extra.get("order") == 0
    assert param.description == "some description"


def test_param_requires_at_least_order_and_description():
    with pytest.raises(TypeError):
        Param()

    with pytest.raises(TypeError):
        Param(order=0)

    with pytest.raises(TypeError):
        Param(description="some description")


def test_param_values_list_defaults_to_empty_list():
    p = Param(0, "desc")
    assert p.extra.get("values_list") == []


def test_param_contains_defaults_to_empty_list():
    p = Param(0, "desc")
    assert p.extra.get("contains") == []
