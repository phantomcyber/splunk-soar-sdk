from unittest import mock

from soar_sdk.action_results import ActionOutput
from soar_sdk.app import App
from soar_sdk.input_spec import InputSpecification
from soar_sdk.params import Params
import pytest


def test_app_run(example_app):
    with mock.patch("soar_sdk.app_cli_runner.AppCliRunner.run") as run_mock:
        example_app.cli()

    assert run_mock.called


def test_handle(example_app: App, simple_action_input: InputSpecification):
    with mock.patch.object(example_app.actions_provider, "handle") as mock_handle:
        example_app.handle(simple_action_input.json())

    mock_handle.assert_called_once()


def test_get_actions(example_app: App):
    @example_app.action()
    def action_handler(params: Params) -> ActionOutput:
        pass

    actions = example_app.get_actions()
    assert len(actions) == 1
    assert "action_handler" in actions
    assert actions["action_handler"] == action_handler


def test_app_asset(app_with_simple_asset: App):
    """asset is a property which lazily parses the raw config on first access.
    Assert that it is not built until accessed, and it is built exactly once"""

    app_with_simple_asset._raw_asset_config = {"base_url": "https://example.com"}

    assert not hasattr(app_with_simple_asset, "_asset")
    asset = app_with_simple_asset.asset
    assert asset.base_url == "https://example.com"
    assert hasattr(app_with_simple_asset, "_asset")
    assert app_with_simple_asset.asset is asset


def test_appid_not_uuid():
    with pytest.raises(ValueError, match="Appid is not a valid uuid: invalid"):
        App(
            name="example_app",
            appid="invalid",
            app_type="sandbox",
            product_vendor="Splunk Inc.",
            logo="logo.svg",
            logo_dark="logo_dark.svg",
            product_name="Example App",
            publisher="Splunk Inc.",
        )

    with pytest.raises(
        ValueError,
        match="Appid is not a valid uuid: 00000000000000000000000000000000",
    ):
        App(
            name="example_app",
            appid="00000000000000000000000000000000",
            app_type="sandbox",
            product_vendor="Splunk Inc.",
            logo="logo.svg",
            logo_dark="logo_dark.svg",
            product_name="Example App",
            publisher="Splunk Inc.",
        )
