import pytest
from pydantic import Field

from soar_sdk.asset import AssetField, AssetFieldSpecification, BaseAsset, FieldCategory
from soar_sdk.exceptions import AppContextRequired


def test_asset_with_aliased_field():
    """Ensure that asset field serialization uses the field alias if available, not the name."""

    class AliasedAsset(BaseAsset):
        aliased_field: str = AssetField(alias="_aliased_field")

    result = AliasedAsset.to_json_schema()
    assert result["_aliased_field"] == AssetFieldSpecification(
        data_type="string",
        required=True,
        description="Aliased Field",
        order=0,
        category=FieldCategory.CONNECTIVITY,
    )


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


def test_fields_requiring_decryption():
    """
    Test that fields requiring decryption are correctly identified.
    """

    class AssetWithSensitiveFields(BaseAsset):
        sensitive_field: str = AssetField(sensitive=True)
        normal_field: str = AssetField()

    assert AssetWithSensitiveFields.fields_requiring_decryption() == {"sensitive_field"}


def test_asset_field_none_annotation():
    class TestAsset(BaseAsset):
        field_with_type: str

    TestAsset.model_fields["field_with_type"].annotation = None
    schema = TestAsset.to_json_schema()
    assert "field_with_type" not in schema


def test_asset_field_with_none_values():
    class TestAsset(BaseAsset):
        field1: str = AssetField(required=None, sensitive=None)

    # This should work without errors - None values for optional params
    schema = TestAsset.to_json_schema()
    assert "field1" in schema


def test_asset_state_unavailable_outside_action():
    with pytest.raises(AppContextRequired):
        _ = BaseAsset().auth_state
    with pytest.raises(AppContextRequired):
        _ = BaseAsset().cache_state
    with pytest.raises(AppContextRequired):
        _ = BaseAsset().ingest_state
