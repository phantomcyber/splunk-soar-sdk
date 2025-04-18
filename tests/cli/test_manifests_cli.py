import json
import os
import tempfile
from unittest import mock

import pytest
from typer.testing import CliRunner

from soar_sdk.cli.manifests.cli import manifests
from soar_sdk.cli.manifests.processors import ManifestProcessor


# Create a test runner
runner = CliRunner()


@pytest.fixture
def temp_manifest_file():
    """Create a temporary manifest file for testing."""
    # Create a temporary file with sample manifest data
    with tempfile.NamedTemporaryFile(delete=False, mode="w+") as temp_file:
        test_data = {
            "name": "test-app",
            "version": "1.0.0",
            "description": "A test app",
        }
        json.dump(test_data, temp_file)
        temp_file_path = temp_file.name

    yield temp_file_path

    # Clean up the temporary file
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)


def test_manifests_display_command(temp_manifest_file):
    """Test the manifest display command with a temporary manifest file."""
    result = runner.invoke(manifests, ["display", temp_manifest_file])

    # Verify the command executed successfully
    assert result.exit_code == 0

    # Verify output contains expected manifest data
    assert "'name': 'test-app'" in result.stdout
    assert "'version': '1.0.0'" in result.stdout
    assert "'description': 'A test app'" in result.stdout


def test_manifests_create_command(temp_manifest_file):
    """Test the manifest create command with a temporary manifest file."""
    # Mock the ManifestProcessor.create method to avoid actual file creation
    with mock.patch.object(ManifestProcessor, "create") as mock_create:
        project_context = "test_context"
        result = runner.invoke(
            manifests, ["create", temp_manifest_file, project_context]
        )

        # Verify the command executed successfully
        assert result.exit_code == 0
        mock_create.assert_called_once()


def test_manifests_create_command_executes_creation():
    """Test that the create command actually executes the manifest creation process."""
    with tempfile.NamedTemporaryFile(delete=False) as output_file:
        output_path = output_file.name

    try:
        with tempfile.TemporaryDirectory() as project_dir:
            # Create a manifest processor that will actually run
            with mock.patch.object(
                ManifestProcessor, "__init__", return_value=None
            ) as mock_init:
                with mock.patch.object(ManifestProcessor, "create") as mock_create:
                    # Run the command
                    result = runner.invoke(
                        manifests, ["create", output_path, project_dir]
                    )

                    # Verify command executed successfully
                    assert result.exit_code == 0

                    # Verify processor was initialized with correct parameters
                    mock_init.assert_called_once_with(output_path, project_dir)

                    # Verify create method was called
                    mock_create.assert_called_once()
    finally:
        # Clean up the temporary output file
        if os.path.exists(output_path):
            os.unlink(output_path)
