from pydantic import Field
import pytest

from soar_sdk.asset import AssetField, BaseAsset


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

    class InvalidAsset(BaseAsset):
        _reserved_field: str

    with pytest.raises(ValueError, match=r".+starts with.+not allowed"):
        InvalidAsset(_reserved_field="test")


def test_asset_implicitly_reserved_config_field_validation():
    """
    Test that subclasses of BaseAsset cannot define fields that are implicitly reserved by the platform.
    """

    class AppVersion(BaseAsset):
        app_version: str = ""

    class Directory(BaseAsset):
        directory: str = ""

    class Ingest(BaseAsset):
        ingest: dict = Field(default_factory=dict)

    class MainModule(BaseAsset):
        main_module: str = ""

    class Appname(BaseAsset):
        appname: str = ""

    for asset_class in (
        AppVersion,
        Directory,
        Ingest,
        MainModule,
        Appname,
    ):
        with pytest.raises(ValueError, match="is reserved by the platform"):
            asset_class()


def test_sensitive_field_must_be_str():
    class BrokenPassword(BaseAsset):
        secret: bool = AssetField(sensitive=True)

    with pytest.raises(TypeError, match="must be type str"):
        BrokenPassword.to_json_schema()


def test_bad_datatype():
    class BadDatatype(BaseAsset):
        bad: list

    with pytest.raises(TypeError, match="Unsupported field type: list"):
        BadDatatype.to_json_schema()
