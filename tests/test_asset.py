import pytest

from soar_sdk.asset import BaseAsset


def test_asset_reserved_field_validation():
    """Test that subclasses of BaseAsset cannot define fields starting with '_reserved_'."""

    # This should be fine
    class ValidAsset(BaseAsset):
        normal_field: str
        another_field: int

    try:
        ValidAsset(normal_field="test", another_field=42)
    except ValueError:
        pytest.fail("ValidAsset should not raise a ValueError")

    # This should raise a ValidationError
    class InvalidAsset(BaseAsset):
        _reserved_field: str

    with pytest.raises(ValueError, match=r".+starts with.+not allowed"):
        InvalidAsset(_reserved_field="test")
