from io import BytesIO
from unittest import mock
import json
from pathlib import Path
import pytest
from collections.abc import Iterator
from typing import TextIO

from soar_sdk.app import App
from soar_sdk.app_cli_runner import AppCliRunner
import os

from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse


@pytest.fixture
def tmp_asset_and_param_files(tmp_path: Path) -> Iterator[TextIO, TextIO]:
    """Fixture to create temporary asset and parameter files, already opened for writing."""
    asset_file = tmp_path / "asset.json"
    param_file = tmp_path / "params.json"

    with asset_file.open("w") as af, param_file.open("w") as pf:
        yield af, pf


def test_parse_args_with_no_actions(simple_app: App):
    """Test parsing arguments when app has no actions."""
    runner = AppCliRunner(simple_app)

    # Mock get_actions to return an empty dict
    runner.app.actions_provider.get_actions = mock.Mock(return_value={})

    # Calling parse_args with no argv should raise SystemExit because subparser is required
    with pytest.raises(SystemExit):
        runner.parse_args([])


def test_parse_args_with_action_no_params(app_with_action: App):
    """Test parsing arguments for an action that doesn't require params or asset."""
    runner = AppCliRunner(app_with_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action")
    assert action is not None

    # Modify the action to not require params
    action.params_class = None

    # Parse args with our action
    args = runner.parse_args(["action", "test_action"])

    # Verify the returned args have the expected values
    assert args.identifier == "test_action"
    assert args.action == action
    assert not args.needs_asset


def test_parse_args_with_action_needs_asset(
    app_with_asset_action: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test parsing arguments for an action that requires an asset file."""
    runner = AppCliRunner(app_with_asset_action)
    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action_with_asset")
    assert action is not None

    asset_file, param_file = tmp_asset_and_param_files

    asset_json = {"key": "value"}
    json.dump(asset_json, asset_file)
    asset_file.flush()

    param_json = {"field1": 42}
    json.dump(param_json, param_file)
    param_file.flush()

    # Parse args with our action and asset file
    args = runner.parse_args(
        [
            "action",
            "test_action_with_asset",
            "--asset-file",
            asset_file.name,
            "--param-file",
            param_file.name,
        ]
    )

    # Verify the returned args have the expected values
    assert args.identifier == "test_action_with_asset"
    assert args.action == action
    assert args.needs_asset
    assert args.asset_file == Path(asset_file.name)


def test_parse_args_with_action_needs_params(
    app_with_action: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test parsing arguments for an action that requires parameters."""
    runner = AppCliRunner(app_with_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action")
    assert action is not None

    _, param_file = tmp_asset_and_param_files

    param_json = {"field1": 42}
    json.dump(param_json, param_file)
    param_file.flush()

    # Parse args with our action and param file
    args = runner.parse_args(["action", "test_action", "--param-file", param_file.name])

    # Verify the returned args have the expected values
    assert args.identifier == "test_action"
    assert args.action == action
    assert not args.needs_asset
    assert args.param_file == Path(param_file.name)

    # Verify that raw_input_data is properly created
    input_data = json.loads(args.raw_input_data)
    assert input_data["action"] == "test_action"
    assert input_data["identifier"] == "test_action"
    assert input_data["config"]["app_version"] == "1.0.0"
    assert len(input_data["parameters"]) == 1
    assert input_data["parameters"][0]["field1"] == 42


def test_parse_args_with_action_needs_asset_and_params(
    app_with_asset_action: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test parsing arguments for an action that requires both asset and parameters."""
    runner = AppCliRunner(app_with_asset_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action_with_asset")
    assert action is not None

    asset_file, param_file = tmp_asset_and_param_files

    asset_json = {"asset_key": "asset_value"}
    json.dump(asset_json, asset_file)
    asset_file.flush()

    param_json = {"field1": 99}
    json.dump(param_json, param_file)
    param_file.flush()

    # Parse args with our action, asset file and param file
    args = runner.parse_args(
        [
            "action",
            "test_action_with_asset",
            "--asset-file",
            asset_file.name,
            "--param-file",
            param_file.name,
        ]
    )

    # Verify the returned args have the expected values
    assert args.identifier == "test_action_with_asset"
    assert args.action == action
    assert args.needs_asset
    assert args.asset_file == Path(asset_file.name)
    assert args.param_file == Path(param_file.name)

    # Verify that raw_input_data is properly created with asset data
    input_data = json.loads(args.raw_input_data)
    assert input_data["action"] == "test_action_with_asset"
    assert input_data["identifier"] == "test_action_with_asset"
    assert input_data["config"]["app_version"] == "1.0.0"
    assert input_data["config"]["asset_key"] == "asset_value"
    assert "parameters" in input_data
    if action.params_class:  # Check if the action actually has params
        assert len(input_data["parameters"]) == 1
        assert input_data["parameters"][0]["field1"] == 99


def test_parse_args_with_invalid_param_file(
    app_with_action: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test parsing arguments with an invalid parameter file."""
    runner = AppCliRunner(app_with_action)

    _, param_file = tmp_asset_and_param_files

    # Create a temporary param file with invalid JSON content
    param_file.write("this is not valid json")
    param_file.flush()

    # Parsing args with invalid param file should raise SystemExit
    with pytest.raises(SystemExit):
        runner.parse_args(["action", "test_action", "--param-file", param_file.name])


def test_parse_args_with_invalid_asset_file(
    app_with_asset_action: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test parsing arguments with an invalid asset file."""
    runner = AppCliRunner(app_with_asset_action)

    asset_file, _ = tmp_asset_and_param_files

    # Create a temporary asset file with invalid JSON content
    asset_file.write("this is not valid json")
    asset_file.flush()

    # Parsing args with invalid asset file should raise SystemExit
    with pytest.raises(SystemExit):
        runner.parse_args(
            ["action", "test_action_with_asset", "--asset-file", asset_file.name]
        )


def test_parse_args_with_malformed_param_values(
    app_with_action: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test parsing arguments with valid JSON but invalid parameter values."""
    runner = AppCliRunner(app_with_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action")
    assert action is not None
    assert action.params_class is not None

    # Mock the parse_obj method to raise a validation error
    validation_error = ValueError("Field 'field1' expected int, got str")
    action.params_class.parse_obj = mock.Mock(side_effect=validation_error)

    param_file, _ = tmp_asset_and_param_files

    # Create a temporary param file with valid JSON but incompatible data types
    param_json = {"field1": "not_an_integer"}  # field1 expects an integer
    json.dump(param_json, param_file)
    param_file.flush()

    # Parsing args with invalid param values should raise SystemExit
    with pytest.raises(SystemExit):
        runner.parse_args(["action", "test_action", "--param-file", param_file.name])


def test_with_soar_authentication(
    app_with_action: App, mock_get_any_soar_call, mock_post_any_soar_call
):
    """Test parsing arguments for an action that requires both asset and parameters."""
    runner = AppCliRunner(app_with_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action")
    assert action is not None
    action.params_class = None
    os.environ["PHANTOM_PASSWORD"] = "password"

    args = runner.parse_args(
        [
            "--soar-url",
            "10.34.5.6",
            "--soar-user",
            "soar_local_admin",
            "action",
            "test_action",
        ]
    )
    del os.environ["PHANTOM_PASSWORD"]

    assert args.soar_url == "10.34.5.6"
    assert args.soar_user == "soar_local_admin"
    assert args.soar_password == "password"

    input_data = json.loads(args.raw_input_data)
    assert input_data["soar_auth"]["phantom_url"] == "https://10.34.5.6"
    assert input_data["soar_auth"]["username"] == "soar_local_admin"
    assert input_data["soar_auth"]["password"] == "password"


def test_bas_soar_auth_params(app_with_action: App):
    """Test parsing arguments for an action that requires both asset and parameters."""
    runner = AppCliRunner(app_with_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action")
    assert action is not None
    action.params_class = None

    with pytest.raises(SystemExit):
        runner.parse_args(
            [
                "--soar-url",
                "10.34.5.6",
                "--soar-user",
                "soar_local_admin",
                "action",
                "test_action",
            ]
        )


def test_parse_args_webhook(
    app_with_asset_webhook: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test parsing arguments for a webhook."""
    runner = AppCliRunner(app_with_asset_webhook)

    asset_file, _ = tmp_asset_and_param_files
    asset_json = {"asset_key": "asset_value"}
    json.dump(asset_json, asset_file)
    asset_file.flush()

    args = runner.parse_args(
        [
            "webhook",
            "test_webhook",
            "--asset-file",
            asset_file.name,
        ]
    )

    assert args.webhook_request == WebhookRequest(
        method="GET",
        headers={},
        path_parts=["test_webhook"],
        query={},
        body=None,
        asset={"asset_key": "asset_value"},
        soar_base_url="https://example.com",
        soar_auth_token="PLACEHOLDER",
        asset_id=1,
    )


def test_parse_args_webhook_headers(
    app_with_asset_webhook: App, tmp_asset_and_param_files
):
    """Test parsing arguments for a webhook with request headers."""
    runner = AppCliRunner(app_with_asset_webhook)

    asset_file, _ = tmp_asset_and_param_files

    # Parsing args with an invalid header should raise SystemExit
    asset_json = {"asset_key": "asset_value"}
    json.dump(asset_json, asset_file)
    asset_file.flush()

    args = runner.parse_args(
        [
            "webhook",
            "test_webhook",
            "--asset-file",
            asset_file.name,
            "--header",
            "Content-Type=application/json",
        ]
    )

    assert args.webhook_request == WebhookRequest(
        method="GET",
        headers={"Content-Type": "application/json"},
        path_parts=["test_webhook"],
        query={},
        body=None,
        asset={"asset_key": "asset_value"},
        soar_base_url="https://example.com",
        soar_auth_token="PLACEHOLDER",
        asset_id=1,
    )


def test_parse_args_webhook_invalid_header(
    app_with_asset_webhook: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test parsing arguments for a webhook with an invalid header."""
    runner = AppCliRunner(app_with_asset_webhook)

    asset_file, _ = tmp_asset_and_param_files

    # Parsing args with an invalid header should raise SystemExit
    asset_json = {"asset_key": "asset_value"}
    json.dump(asset_json, asset_file)
    asset_file.flush()

    with (
        pytest.raises(SystemExit),
    ):
        runner.parse_args(
            [
                "webhook",
                "test_webhook",
                "--asset-file",
                asset_file.name,
                "--header",
                "InvalidHeaderFormat",  # Missing '='
            ]
        )


def test_parse_args_webhook_flattens_params(
    app_with_asset_webhook: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test parsing arguments for a webhook."""
    runner = AppCliRunner(app_with_asset_webhook)

    asset_file, _ = tmp_asset_and_param_files
    asset_json = {"asset_key": "asset_value"}
    json.dump(asset_json, asset_file)
    asset_file.flush()

    args = runner.parse_args(
        [
            "webhook",
            "test_webhook?key1=value1&key2=value2&key2=value3",
            "--asset-file",
            asset_file.name,
        ]
    )

    assert args.webhook_request == WebhookRequest(
        method="GET",
        headers={},
        path_parts=["test_webhook"],
        query={
            "key1": ["value1"],
            "key2": ["value2", "value3"],
        },
        body=None,
        asset={"asset_key": "asset_value"},
        soar_base_url="https://example.com",
        soar_auth_token="PLACEHOLDER",
        asset_id=1,
    )


def test_run_action_cli(app_with_action: App):
    """Test running an action via CLI."""
    runner = AppCliRunner(app_with_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action")
    assert action is not None

    # Modify the action to not require params
    action.params_class = None

    # Mock the app's handle method to return a specific result
    app_with_action.handle = mock.Mock(return_value={"result": "success"})

    args = runner.parse_args(["action", "test_action"])
    runner.parse_args = mock.Mock(return_value=args)

    # Run the action
    runner.run()

    # Verify the result
    app_with_action.handle.assert_called_once_with(args.raw_input_data)


def test_run_webhook_cli(
    app_with_asset_webhook: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test running a webhook via CLI."""
    runner = AppCliRunner(app_with_asset_webhook)

    asset_file, _ = tmp_asset_and_param_files

    asset_json = {"asset_key": "asset_value"}
    json.dump(asset_json, asset_file)
    asset_file.flush()

    args = runner.parse_args(["webhook", "test_webhook", "-a", asset_file.name])
    runner.parse_args = mock.Mock(return_value=args)

    # Run the webhook
    runner.run()


def test_run_webhook_cli_base64(
    app_with_asset_webhook: App, tmp_asset_and_param_files: tuple[Path, Path]
):
    """Test running a webhook via CLI."""

    @app_with_asset_webhook.webhook("test_binary_webhook")
    def test_binary_webhook(request: WebhookRequest) -> WebhookResponse:
        return WebhookResponse.file_response(
            fd=BytesIO(b"Test content"),
            filename="test_file.txt",
            status_code=200,
            extra_headers={"X-Custom-Header": "CustomValue"},
        )

    runner = AppCliRunner(app_with_asset_webhook)

    asset_file, _ = tmp_asset_and_param_files

    asset_json = {"asset_key": "asset_value"}
    json.dump(asset_json, asset_file)
    asset_file.flush()

    args = runner.parse_args(["webhook", "test_binary_webhook", "-a", asset_file.name])
    runner.parse_args = mock.Mock(return_value=args)

    # Run the webhook
    runner.run()
