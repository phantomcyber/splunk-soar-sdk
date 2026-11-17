import pytest

from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.meta.app import AppMeta
from soar_sdk.params import Param, Params


def make_manifest(actions: list[ActionMeta]) -> dict:
    return AppMeta(
        description="Schema contract example",
        app_version="1.0.0",
        license="Apache-2.0",
        package_name="schema_example",
        project_name="schema-example",
        actions=actions,
    ).to_json_manifest()


def test_manifest_maps_schemas_by_action_name_and_keeps_legacy_actions():
    class LookupParams(Params):
        domain: str = Param(cef_types=["domain"], primary=True)

    class LookupOutput(ActionOutput):
        email: str | None = OutputField(cef_types=["email"])

    action = ActionMeta(
        action="whois domain",
        identifier="lookup_domain",
        description="Look up a domain",
        type="investigate",
        read_only=True,
        parameters=LookupParams,
        output=LookupOutput,
    )
    manifest = make_manifest([action])
    schemas = manifest["actionSchemasLookup"]["whois domain"]

    assert "lookup_domain" not in manifest["actionSchemasLookup"]
    assert set(schemas) == {"inputSchema", "outputSchema"}
    assert schemas["inputSchema"]["required"] == ["domain"]
    assert schemas["inputSchema"]["properties"]["domain"]["x-soar-primary"] is True
    assert schemas["inputSchema"]["properties"]["domain"]["x-soar-contains"] == [
        "domain"
    ]
    fields = schemas["outputSchema"]["$defs"]["LookupOutput"]["properties"]
    assert fields["email"]["type"] == ["string", "null"]
    assert "default" not in fields["email"]
    assert fields["email"]["x-soar-contains"] == ["email"]
    legacy = manifest["actions"][0]
    assert legacy["identifier"] == "lookup_domain"
    assert "outputSchema" not in legacy
    assert "outputSchemaMetadata" not in legacy
    assert any(
        item["data_path"] == "action_result.data.*.email" for item in legacy["output"]
    )


def test_manifest_without_actions_has_an_empty_schema_map():
    manifest = make_manifest([])
    assert manifest["actions"] == []
    assert manifest["actionSchemasLookup"] == {}


@pytest.mark.parametrize("name", ["", " "])
def test_manifest_rejects_empty_action_schema_names(name):
    action = ActionMeta(
        action=name,
        identifier="lookup",
        description="Lookup",
        type="investigate",
        read_only=True,
    )
    with pytest.raises(ValueError, match="Action schema names must not be empty"):
        make_manifest([action])


def test_manifest_rejects_duplicate_action_schema_names():
    actions = [
        ActionMeta(
            action="lookup",
            identifier=identifier,
            description="Lookup",
            type="investigate",
            read_only=True,
        )
        for identifier in ("lookup_v1", "lookup_v2")
    ]
    with pytest.raises(ValueError, match="Duplicate action schema name: 'lookup'"):
        make_manifest(actions)
