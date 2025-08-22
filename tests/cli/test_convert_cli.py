from unittest.mock import patch
import pytest
from pathlib import Path
import ast
import json

from typer.testing import CliRunner

from soar_sdk.meta.actions import ActionMeta
from soar_sdk.meta.app import AppMeta, AssetFieldSpecification

from soar_sdk.cli.init import cli


@pytest.fixture
def runner():
    return CliRunner()


parent_dir = Path(__file__).parent
asset_dir = parent_dir / "test_assets" / "converted_app"


@pytest.fixture
def app_meta():
    return AppMeta(
        name="test_app",
        description="A test app",
        app_version="1.0.0",
        package_name="test_app",
        main_module="src/app.py:app",
        logo="logo.svg",
        logo_dark="logo_dark.svg",
        product_name="Test Product",
        python_version=["3.9", "3.13"],
        project_name="test_app",
        license="Copyright (c) 2025 Splunk Inc.",
    )


def test_generate_asset_definition(app_meta, tmp_path):
    """Test that convert command generates the expected asset definition."""
    app_py_path = tmp_path / "app.py"
    app_py_path.write_text("class Asset(BaseAsset):\n    pass")

    app_meta.configuration = {
        "username": AssetFieldSpecification(
            label="Username",
            description="The username for the application",
            required=True,
            data_type="string",
        ),
        "placeholder": AssetFieldSpecification(
            label="Placeholder",
            required=False,
            data_type="ph",
        ),
        "color": AssetFieldSpecification(
            label="Color",
            required=False,
            data_type="string",
            default="blue",
            value_list=["red", "green", "blue"],
        ),
        "timezone": AssetFieldSpecification(
            label="Timezone",
            required=False,
            data_type="timezone",
            default="UTC",
        ),
    }
    asset_class = cli.generate_asset_definition_ast(app_meta=app_meta)

    definition = ast.unparse(asset_class)
    expected_definition = "\n".join(
        [
            "class Asset(BaseAsset):",
            "    username: str = AssetField(required=True, description='The username for the application')",
            "    color: str = AssetField(required=False, default='blue', value_list=['red', 'green', 'blue'])",
            "    timezone: ZoneInfo = AssetField(required=False, default=ZoneInfo('UTC'))",
        ]
    )

    assert expected_definition == definition


def test_generate_asset_definition_with_no_fields(app_meta, tmp_path):
    """Test that convert command generates an empty asset definition when no fields are provided."""
    app_py_path = tmp_path / "app.py"
    app_py_path.write_text("class Asset(BaseAsset):\n    pass")

    app_meta.configuration = {}
    asset_class = cli.generate_asset_definition_ast(app_meta=app_meta)

    definition = ast.unparse(asset_class)
    expected_definition = "\n".join(
        [
            "class Asset(BaseAsset):",
            "    pass",
        ]
    )

    assert expected_definition == definition


def test_generate_action_definitions(app_meta, tmp_path):
    """Test that convert command generates the expected action definitions."""
    app_py_path = tmp_path / "app.py"
    app_py_path.write_text('if __name__ == "__main__":\n')

    app_meta.actions = [
        ActionMeta(
            action="send message",
            identifier="send_message",
            description="Send a message",
            type="test",
            read_only=False,
            verbose="This is a test action",
        ),
        ActionMeta(
            action="test connectivity",
            identifier="test_connectivity",
            description="Test connectivity to the application",
            type="test",
            read_only=True,
        ),
    ]
    actions = cli.generate_action_definitions_ast(app_meta=app_meta)
    action_names = set(action.name for action in actions)

    assert action_names == {"send_message", "test_connectivity"}


def test_convert_cli(runner, tmp_path, app_meta):
    """Test that convert command generates the expected app structure."""

    app_meta.configuration = {
        "username": AssetFieldSpecification(
            label="Username",
            description="The username for the application",
            required=True,
            data_type="string",
        )
    }

    app_dir = tmp_path / "test_app"
    app_dir.mkdir()
    (app_dir / "app.json").write_text(app_meta.json())
    (app_dir / app_meta.logo).touch()
    (app_dir / app_meta.logo_dark).touch()

    output_dir = tmp_path / "output"

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            cli.convert,
            [
                str(app_dir),
                str(output_dir),
            ],
        )

    print(result.output)  # For debugging purposes

    assert result.exit_code == 0
    assert (output_dir / "src").is_dir()
    assert (output_dir / "src" / "__init__.py").exists()
    assert (output_dir / "src" / "app.py").exists()
    assert (output_dir / "pyproject.toml").exists()
    assert (output_dir / "logo.svg").exists()
    assert (output_dir / "logo_dark.svg").exists()


def test_convert_cli_with_default_output(runner, tmp_path, app_meta):
    """Test that convert command uses default output directory if not specified."""

    app_meta.configuration = {
        "username": AssetFieldSpecification(
            label="Username",
            description="The username for the application",
            required=True,
            data_type="string",
        )
    }

    app_dir = tmp_path / "test_app"
    app_dir.mkdir()
    (app_dir / "app.json").write_text(app_meta.json())
    (app_dir / app_meta.logo).touch()
    (app_dir / app_meta.logo_dark).touch()

    output_dir = app_dir / "sdk_app"

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            cli.convert,
            [str(app_dir)],
        )

    print(result.output)  # For debugging purposes

    assert result.exit_code == 0
    assert (output_dir / "src").is_dir()
    assert (output_dir / "src" / "__init__.py").exists()
    assert (output_dir / "src" / "app.py").exists()
    assert (output_dir / "pyproject.toml").exists()
    assert (output_dir / "logo.svg").exists()
    assert (output_dir / "logo_dark.svg").exists()


def test_convert_cli_with_custom_view(runner, tmp_path, app_meta):
    """Test that convert command handles custom views correctly."""

    app_meta_dict = app_meta.dict()
    app_meta_dict["actions"] = [
        {
            "action": "custom view action",
            "identifier": "custom_view_action",
            "description": "An action with a custom view",
            "type": "test",
            "read_only": False,
            "verbose": "This action has a custom view",
            "render": {
                "type": "custom",
            },
        }
    ]

    app_dir = tmp_path / "test_app"
    app_dir.mkdir()
    (app_dir / "app.json").write_text(json.dumps(app_meta_dict, indent=4))
    (app_dir / app_meta.logo).touch()
    (app_dir / app_meta.logo_dark).touch()

    output_dir = tmp_path / "output"

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            cli.convert,
            [
                str(app_dir),
                str(output_dir),
            ],
        )

    print(result.output)  # For debugging purposes

    assert (
        "The following actions have custom views: custom_view_action" in result.output
    )
    assert result.exit_code == 0


def test_convert_cli_with_rest_handler(runner, tmp_path, app_meta):
    """Test that convert command handles REST handlers correctly."""

    app_meta_dict = app_meta.dict()
    app_meta_dict["rest_handler"] = "my_connector.rest_handler"

    app_dir = tmp_path / "test_app"
    app_dir.mkdir()
    (app_dir / "app.json").write_text(json.dumps(app_meta_dict, indent=4))
    (app_dir / app_meta.logo).touch()
    (app_dir / app_meta.logo_dark).touch()

    output_dir = tmp_path / "output"

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            cli.convert,
            [
                str(app_dir),
                str(output_dir),
            ],
        )

    print(result.output)  # For debugging purposes

    assert "The app has REST handlers defined." in result.output
    assert result.exit_code == 0


def test_convert_cli_with_webhooks(runner, tmp_path, app_meta):
    """Test that convert command handles webhooks correctly."""

    app_meta_dict = app_meta.dict()
    app_meta_dict["webhooks"] = {
        "handler": "my_connector.webhook_handler",
    }

    app_dir = tmp_path / "test_app"
    app_dir.mkdir()
    (app_dir / "app.json").write_text(json.dumps(app_meta_dict, indent=4))
    (app_dir / app_meta.logo).touch()
    (app_dir / app_meta.logo_dark).touch()

    output_dir = tmp_path / "output"

    with patch("subprocess.run"), patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/example"

        result = runner.invoke(
            cli.convert,
            [
                str(app_dir),
                str(output_dir),
            ],
        )

    print(result.output)  # For debugging purposes

    assert "The app has Webhooks defined." in result.output
    assert result.exit_code == 0
