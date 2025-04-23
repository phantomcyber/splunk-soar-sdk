from unittest import mock
import json
import tempfile
from pathlib import Path
import pytest

from soar_sdk.app import App
from soar_sdk.app_cli_runner import AppCliRunner


def test_app_cli(simple_app: App):
    runner = AppCliRunner(simple_app)
    runner.parse_args = mock.Mock()
    runner.app.handle = mock.Mock(return_value="{}")

    runner.run()

    assert runner.parse_args.call_count == 1
    assert runner.app.handle.call_count == 1


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
    args = runner.parse_args(["test_action"])

    # Verify the returned args have the expected values
    assert args.identifier == "test_action"
    assert args.action == action
    assert not args.needs_asset


def test_parse_args_with_action_needs_asset(app_with_asset_action: App):
    """Test parsing arguments for an action that requires an asset file."""
    runner = AppCliRunner(app_with_asset_action)
    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action_with_asset")
    assert action is not None

    # Create temporary files for asset and params
    with (
        tempfile.NamedTemporaryFile(suffix=".json", mode="w+") as asset_file,
        tempfile.NamedTemporaryFile(suffix=".json", mode="w+") as param_file,
    ):
        asset_json = {"key": "value"}
        json.dump(asset_json, asset_file)
        asset_file.flush()

        param_json = {"field1": 42}
        json.dump(param_json, param_file)
        param_file.flush()

        # Parse args with our action and asset file
        args = runner.parse_args(
            [
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


def test_parse_args_with_action_needs_params(app_with_action: App):
    """Test parsing arguments for an action that requires parameters."""
    runner = AppCliRunner(app_with_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action")
    assert action is not None

    # Create a temporary param file with some JSON content
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w+") as param_file:
        param_json = {"field1": 42}
        json.dump(param_json, param_file)
        param_file.flush()

        # Parse args with our action and param file
        args = runner.parse_args(["test_action", "--param-file", param_file.name])

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


def test_parse_args_with_action_needs_asset_and_params(app_with_asset_action: App):
    """Test parsing arguments for an action that requires both asset and parameters."""
    runner = AppCliRunner(app_with_asset_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action_with_asset")
    assert action is not None

    # Create temporary files for asset and params
    with (
        tempfile.NamedTemporaryFile(suffix=".json", mode="w+") as asset_file,
        tempfile.NamedTemporaryFile(suffix=".json", mode="w+") as param_file,
    ):
        asset_json = {"asset_key": "asset_value"}
        json.dump(asset_json, asset_file)
        asset_file.flush()

        param_json = {"field1": 99}
        json.dump(param_json, param_file)
        param_file.flush()

        # Parse args with our action, asset file and param file
        args = runner.parse_args(
            [
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


def test_parse_args_with_invalid_param_file(app_with_action: App):
    """Test parsing arguments with an invalid parameter file."""
    runner = AppCliRunner(app_with_action)

    # Create a temporary param file with invalid JSON content
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w+") as param_file:
        param_file.write("this is not valid json")
        param_file.flush()

        # Parsing args with invalid param file should raise SystemExit
        with pytest.raises(SystemExit):
            runner.parse_args(["test_action", "--param-file", param_file.name])


def test_parse_args_with_invalid_asset_file(app_with_asset_action: App):
    """Test parsing arguments with an invalid asset file."""
    runner = AppCliRunner(app_with_asset_action)

    # Create a temporary asset file with invalid JSON content
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w+") as asset_file:
        asset_file.write("this is not valid json")
        asset_file.flush()

        # Parsing args with invalid asset file should raise SystemExit
        with pytest.raises(SystemExit):
            runner.parse_args(
                ["test_action_with_asset", "--asset-file", asset_file.name]
            )


def test_parse_args_with_malformed_param_values(app_with_action: App):
    """Test parsing arguments with valid JSON but invalid parameter values."""
    runner = AppCliRunner(app_with_action)

    # Get the real action from our fixture
    action = runner.app.actions_provider.get_action("test_action")
    assert action is not None
    assert action.params_class is not None

    # Mock the parse_obj method to raise a validation error
    validation_error = ValueError("Field 'field1' expected int, got str")
    action.params_class.parse_obj = mock.Mock(side_effect=validation_error)

    # Create a temporary param file with valid JSON but incompatible data types
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w+") as param_file:
        param_json = {"field1": "not_an_integer"}  # field1 expects an integer
        json.dump(param_json, param_file)
        param_file.flush()

        # Parsing args with invalid param values should raise SystemExit
        with pytest.raises(SystemExit):
            runner.parse_args(["test_action", "--param-file", param_file.name])
