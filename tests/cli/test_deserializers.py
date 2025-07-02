import json
import pytest
from unittest.mock import Mock, patch

from soar_sdk.cli.manifests.deserializers import (
    AppMetaDeserializer,
    ActionDeserializer,
    DeserializedActionMeta,
)
from soar_sdk.cli.manifests.serializers import OutputsSerializer
from soar_sdk.compat import PythonVersion
from soar_sdk.meta.app import AppMeta
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput, OutputFieldSpecification


# Fixtures
@pytest.fixture
def basic_app_data():
    """Basic app.json data structure."""
    return {
        "name": "test_app",
        "description": "Test application",
        "app_version": "1.0.0",
        "package_name": "test_package",
        "license": "MIT",
    }


@pytest.fixture
def create_app_json(tmp_path):
    """Helper fixture to create app.json files."""

    def _create_app_json(data, project_name="test_app"):
        app_json_path = tmp_path / project_name / "app.json"
        app_json_path.parent.mkdir()
        app_json_path.write_text(json.dumps(data))
        return app_json_path

    return _create_app_json


@pytest.fixture
def basic_action_data():
    """Basic action data structure."""
    return {
        "action": "test connectivity",
        "identifier": "test_connectivity",
        "description": "Test connectivity",
        "type": "test",
        "read_only": True,
        "versions": "EQ(*)",
        "parameters": {},
        "output": [],
    }


@pytest.fixture
def mock_action_deserializer():
    """Mock setup for ActionDeserializer methods."""
    with (
        patch.object(ActionDeserializer, "parse_parameters") as mock_parse_params,
        patch.object(ActionDeserializer, "parse_output") as mock_parse_output,
        patch.object(ActionMeta, "parse_obj") as mock_parse_obj,
    ):
        mock_parse_params.return_value = Params
        mock_parse_output.return_value = ActionOutput
        mock_action_meta = Mock(spec=ActionMeta)
        mock_parse_obj.return_value = mock_action_meta

        yield {
            "parse_parameters": mock_parse_params,
            "parse_output": mock_parse_output,
            "parse_obj": mock_parse_obj,
            "action_meta": mock_action_meta,
        }


# AppMetaDeserializer Tests
def test_from_app_json_basic_deserialization(basic_app_data, create_app_json):
    """Test basic deserialization of a minimal app.json file."""
    app_json_path = create_app_json(basic_app_data)

    deserialized_result = AppMetaDeserializer.from_app_json(app_json_path)

    assert not deserialized_result.has_rest_handlers
    assert not deserialized_result.has_webhooks
    assert not deserialized_result.actions_with_custom_views

    result = deserialized_result.app_meta
    assert isinstance(result, AppMeta)
    assert result.name == "test_app"
    assert result.description == "Test application"
    assert result.app_version == "1.0.0"
    assert result.package_name == "test_package"
    assert result.project_name == "test_app"  # Should be derived from parent directory


@pytest.mark.parametrize(
    "python_version_input,expected",
    [
        ("3.9,3.13", [PythonVersion.PY_3_9, PythonVersion.PY_3_13]),
        (["3.9", "3.13"], [PythonVersion.PY_3_9, PythonVersion.PY_3_13]),
        (None, PythonVersion.all()),  # Should use default when None
    ],
)
def test_from_app_json_python_version_handling(
    basic_app_data, create_app_json, python_version_input, expected
):
    """Test various python_version field formats."""
    app_data = basic_app_data.copy()
    if python_version_input is not None:
        app_data["python_version"] = python_version_input

    app_json_path = create_app_json(app_data)
    deserialized_result = AppMetaDeserializer.from_app_json(app_json_path)

    result = deserialized_result.app_meta
    assert result.python_version == expected


def test_from_app_json_python_version_missing(basic_app_data, create_app_json):
    """Test handling when python_version field is missing entirely."""
    app_json_path = create_app_json(basic_app_data)
    deserialized_result = AppMetaDeserializer.from_app_json(app_json_path)

    # Should use default from AppMeta model
    result = deserialized_result.app_meta
    assert result.python_version == PythonVersion.all()


def test_from_app_json_invalid_python_version(basic_app_data, create_app_json):
    """Test handling of invalid python version."""
    app_data = basic_app_data.copy()
    app_data["python_version"] = "3.8"  # Unsupported version

    app_json_path = create_app_json(app_data)

    with pytest.raises(ValueError, match="Unsupported Python version"):
        AppMetaDeserializer.from_app_json(app_json_path)


def test_from_app_json_with_actions(basic_app_data, create_app_json):
    """Test deserialization with actions array."""
    app_data = basic_app_data.copy()
    app_data["actions"] = [
        {
            "action": "test connectivity",
            "identifier": "test_connectivity",
            "description": "Test connectivity",
            "type": "test",
            "read_only": True,
            "versions": "EQ(*)",
            "parameters": {},
            "output": [],
        },
        {
            "action": "custom action",
            "identifier": "custom_action",
            "description": "Custom action",
            "type": "generic",
            "read_only": False,
            "versions": "EQ(*)",
            "parameters": {"param1": {"data_type": "string"}},
            "output": [{"data_path": "action_result.data.*.result"}],
        },
    ]

    app_json_path = create_app_json(app_data)

    with patch.object(ActionDeserializer, "from_action_json") as mock_deserializer:
        mock_action1 = Mock(spec=ActionMeta)
        mock_action2 = Mock(spec=ActionMeta)
        mock_deserializer.side_effect = [
            DeserializedActionMeta(action_meta=mock_action1, has_custom_view=False),
            DeserializedActionMeta(action_meta=mock_action2, has_custom_view=False),
        ]

        deserialized_result = AppMetaDeserializer.from_app_json(app_json_path)

        result = deserialized_result.app_meta
        assert len(result.actions) == 2
        assert mock_deserializer.call_count == 2

        # Check that ActionDeserializer was called with the right data
        call_args = mock_deserializer.call_args_list
        assert call_args[0][0][0]["action"] == "test connectivity"
        assert call_args[1][0][0]["action"] == "custom action"


def test_from_app_json_actions_non_dict_filtered(basic_app_data, create_app_json):
    """Test that non-dict items in actions array are filtered out."""
    app_data = basic_app_data.copy()
    app_data["actions"] = [
        {
            "action": "test connectivity",
            "identifier": "test_connectivity",
            "description": "Test connectivity",
            "type": "test",
            "read_only": True,
            "versions": "EQ(*)",
        },
        "invalid_action_string",
        123,
        {
            "action": "valid action",
            "identifier": "valid_action",
            "description": "Valid action",
            "type": "generic",
            "read_only": False,
            "versions": "EQ(*)",
        },
    ]

    app_json_path = create_app_json(app_data)

    with patch.object(ActionDeserializer, "from_action_json") as mock_deserializer:
        mock_action1 = Mock(spec=ActionMeta)
        mock_action2 = Mock(spec=ActionMeta)
        mock_deserializer.side_effect = [
            DeserializedActionMeta(action_meta=mock_action1, has_custom_view=False),
            DeserializedActionMeta(action_meta=mock_action2, has_custom_view=False),
        ]

        AppMetaDeserializer.from_app_json(app_json_path)

        # Should only process the 2 dict items, not the string or number
        assert mock_deserializer.call_count == 2


@pytest.mark.parametrize(
    "actions_value,expected_count",
    [
        ([], 0),  # Empty array
        (None, 0),  # Missing actions field (handled by get())
    ],
)
def test_from_app_json_actions_edge_cases(
    basic_app_data, create_app_json, actions_value, expected_count
):
    """Test edge cases for actions field."""
    app_data = basic_app_data.copy()
    if actions_value is not None:
        app_data["actions"] = actions_value

    app_json_path = create_app_json(app_data)
    result = AppMetaDeserializer.from_app_json(app_json_path).app_meta

    assert len(result.actions) == expected_count


def test_from_app_json_complex_example(create_app_json):
    """Test with a complex example similar to the provided app.json."""
    app_data = {
        "name": "example_app",
        "description": "This is the basic example SOAR app",
        "appid": "9b388c08-67de-4ca4-817f-26f8fb7cbf55",
        "type": "sandbox",
        "product_vendor": "Splunk Inc.",
        "app_version": "0.1.0",
        "license": "Copyright (c) Splunk Inc., 2025",
        "min_phantom_version": "6.2.2.134",
        "package_name": "phantom_exampleapp",
        "main_module": "src.app:app",
        "logo": "logo.svg",
        "logo_dark": "logo_dark.svg",
        "product_name": "Example App",
        "python_version": ["3.9", "3.13"],
        "product_version_regex": ".*",
        "publisher": "Splunk Inc.",
        "utctime_updated": "2025-04-17T12:00:00.000000Z",
        "fips_compliant": False,
        "contributors": [],
        "configuration": {
            "base_url": {
                "data_type": "string",
                "required": True,
                "description": "Base Url",
                "order": 0,
            }
        },
        "actions": [
            {
                "action": "test connectivity",
                "identifier": "test_connectivity",
                "description": "test connectivity",
                "verbose": "Basic test for app.",
                "type": "test",
                "read_only": True,
                "versions": "EQ(*)",
                "parameters": {},
                "output": [],
            }
        ],
    }

    app_json_path = create_app_json(app_data, "example_app")

    with patch.object(ActionDeserializer, "from_action_json") as mock_deserializer:
        mock_action = Mock(spec=ActionMeta)
        mock_deserializer.return_value = DeserializedActionMeta(
            action_meta=mock_action, has_custom_view=False
        )

        result = AppMetaDeserializer.from_app_json(app_json_path).app_meta

        assert result.name == "example_app"
        assert result.appid == "9b388c08-67de-4ca4-817f-26f8fb7cbf55"
        assert result.product_vendor == "Splunk Inc."
        assert result.python_version == [PythonVersion.PY_3_9, PythonVersion.PY_3_13]
        assert result.project_name == "example_app"
        assert len(result.actions) == 1
        assert result.fips_compliant is False
        assert result.configuration["base_url"]["data_type"] == "string"


@pytest.mark.parametrize(
    "error_type,file_content,expected_exception",
    [
        ("invalid_json", "{ invalid json", json.JSONDecodeError),
        ("file_not_found", None, FileNotFoundError),
    ],
)
def test_from_app_json_error_handling(
    tmp_path, error_type, file_content, expected_exception
):
    """Test error handling for various failure scenarios."""
    if error_type == "file_not_found":
        app_json_path = tmp_path / "nonexistent" / "app.json"
    else:
        app_json_path = tmp_path / "test_app" / "app.json"
        app_json_path.parent.mkdir()
        app_json_path.write_text(file_content)

    with pytest.raises(expected_exception):
        AppMetaDeserializer.from_app_json(app_json_path)


def test_from_app_json_preserves_original_data(basic_app_data, create_app_json):
    """Test that the original manifest data is preserved and passed to AppMeta."""
    app_data = basic_app_data.copy()
    app_data.update(
        {
            "publisher": "Test Publisher",
            "fips_compliant": True,
            "configuration": {
                "tenant": {
                    "description": "Tenant ID",
                    "data_type": "string",
                    "required": True,
                    "order": 0,
                }
            },
        }
    )

    app_json_path = create_app_json(app_data)
    app_meta = AppMetaDeserializer.from_app_json(app_json_path).app_meta

    # Verify that all fields are preserved
    assert app_meta.license == app_data["license"]
    assert app_meta.publisher == app_data["publisher"]
    assert app_meta.fips_compliant is app_data["fips_compliant"]
    assert app_meta.configuration == app_data["configuration"]


def test_from_app_json_project_name_derived_from_path(basic_app_data, create_app_json):
    """Test that project_name is correctly derived from the parent directory name."""
    app_data = basic_app_data.copy()
    app_data["name"] = "different_name"

    app_json_path = create_app_json(app_data, "actual_project_name")
    app_meta = AppMetaDeserializer.from_app_json(app_json_path).app_meta

    # project_name should come from directory name, not the "name" field
    assert app_meta.project_name == "actual_project_name"
    assert app_meta.name == "different_name"  # name field should be preserved


# ActionDeserializer Tests
def test_from_action_json_basic(basic_action_data, mock_action_deserializer):
    """Test basic action deserialization."""
    mocks = mock_action_deserializer

    result = ActionDeserializer.from_action_json(basic_action_data).action_meta

    assert result == mocks["action_meta"]
    mocks["parse_parameters"].assert_called_once_with("test connectivity", {})
    mocks["parse_output"].assert_called_once_with("test connectivity", [])
    assert basic_action_data["parameters"] == Params
    assert basic_action_data["output"] == ActionOutput


def test_from_action_json_with_parameters_and_output(mock_action_deserializer):
    """Test action deserialization with parameters and output."""
    action_data = {
        "action": "custom action",
        "identifier": "custom_action",
        "description": "Custom action",
        "type": "generic",
        "read_only": False,
        "versions": "EQ(*)",
        "parameters": {
            "param1": {
                "data_type": "string",
                "required": True,
                "description": "Test parameter",
            }
        },
        "output": [
            {"data_path": "action_result.data.*.result"},
            {"data_path": "action_result.summary.total_items"},
        ],
    }

    mocks = mock_action_deserializer

    # Capture original parameters and output before they're modified
    original_parameters = action_data["parameters"]
    original_output = action_data["output"]

    result = ActionDeserializer.from_action_json(action_data).action_meta

    assert result == mocks["action_meta"]
    mocks["parse_parameters"].assert_called_once_with(
        "custom action", original_parameters
    )
    mocks["parse_output"].assert_called_once_with("custom action", original_output)


def test_from_action_json_missing_optional_fields(mock_action_deserializer):
    """Test action deserialization when optional fields are missing."""
    action_data = {
        "action": "minimal action",
        "identifier": "minimal_action",
        "description": "Minimal action",
        "type": "generic",
        "read_only": False,
        "versions": "EQ(*)",
        # Missing parameters and output
    }

    mocks = mock_action_deserializer
    result = ActionDeserializer.from_action_json(action_data).action_meta

    assert result == mocks["action_meta"]
    # Should use empty defaults for missing fields
    mocks["parse_parameters"].assert_called_once_with("minimal action", {})
    mocks["parse_output"].assert_called_once_with("minimal action", [])


def test_from_action_json_modifies_action_data_in_place(mock_action_deserializer):
    """Test that from_action_json modifies the action data dictionary in place."""
    action_data = {
        "action": "test action",
        "identifier": "test_action",
        "description": "Test action",
        "type": "test",
        "read_only": True,
        "versions": "EQ(*)",
        "parameters": {"original": "value"},
        "output": [{"data_path": "action_result.data.*.result", "data_type": "string"}],
    }

    mocks = mock_action_deserializer
    original_params = action_data["parameters"]
    original_output = action_data["output"]

    ActionDeserializer.from_action_json(action_data)

    # Verify that the action data was modified in place
    assert action_data["parameters"] is Params  # Should be replaced with class
    assert action_data["output"] is ActionOutput  # Should be replaced with class

    # Verify parse methods were called with original data
    mocks["parse_parameters"].assert_called_once_with("test action", original_params)
    mocks["parse_output"].assert_called_once_with("test action", original_output)


@pytest.mark.parametrize(
    "input_data,expects_base_class",
    [
        (
            {"param1": {"data_type": "string", "required": True}},
            False,
        ),
        ({}, True),
    ],
)
def test_action_deserializer_parse_parameters(input_data, expects_base_class):
    """Test ActionDeserializer parse methods return correct classes."""
    result = ActionDeserializer.parse_parameters("test_action", input_data)

    if expects_base_class:
        # Empty inputs should return base class
        assert result is Params
    else:
        # Non-empty inputs should return dynamic subclass
        assert result is not Params
        assert issubclass(result, Params)
        assert result.__name__ == "TestActionParams"


@pytest.mark.parametrize(
    "input_data,expects_base_class",
    [
        (
            [
                {"data_path": "action_result.data.*.result", "data_type": "string"},
                {"data_path": "action_result.parameter.param1"},
                {"data_path": "action_result.status"},
                {"data_path": "action_result.message"},
            ],
            False,
        ),
        (
            [
                {"data_path": "action_result.parameter.param1"},
                {"data_path": "action_result.status"},
                {"data_path": "action_result.message"},
                {"data_path": "action_result.summary"},
            ],
            True,
        ),
        ([], True),
    ],
)
def test_action_deserializer_parse_methods(input_data, expects_base_class):
    """Test ActionDeserializer parse methods return correct classes."""
    result = ActionDeserializer.parse_output("test_action", input_data)

    if expects_base_class:
        # Empty inputs should return base class
        assert result is ActionOutput
    else:
        # Non-empty inputs should return dynamic subclass
        assert result is not ActionOutput
        assert issubclass(result, ActionOutput)
        assert result.__name__ == "TestActionOutput"


def test_disallows_duplicate_data_paths():
    outputs_def = [
        OutputFieldSpecification(
            data_path="action_result.data.*.result", data_type="string"
        ),
        OutputFieldSpecification(
            data_path="action_result.data.*.result", data_type="password"
        ),
    ]

    with pytest.raises(
        ValueError, match=r"[dD]uplicate.+action_result\.data\.\*\.result"
    ):
        ActionDeserializer.parse_output("test_action", outputs_def)


def test_parse_methods_use_action_name_parameter():
    """Test that parse methods use the action_name parameter to create class names."""
    parameters = {"param1": {"data_type": "string", "required": True}}

    result1 = ActionDeserializer.parse_parameters("action1", parameters)
    result2 = ActionDeserializer.parse_parameters("action2", parameters)

    # Different action names should create different classes
    assert result1 != result2
    assert result1.__name__ == "Action1Params"
    assert result2.__name__ == "Action2Params"

    # Both should be subclasses of Params
    assert issubclass(result1, Params)
    assert issubclass(result2, Params)

    # Same for parse_output

    output_specs: list[OutputFieldSpecification] = [
        {"data_path": "action_result.data.*.result", "data_type": "string"}
    ]

    result1 = ActionDeserializer.parse_output("action1", output_specs)
    result2 = ActionDeserializer.parse_output("action2", output_specs)

    # Different action names should create different classes
    assert result1 != result2
    assert result1.__name__ == "Action1Output"
    assert result2.__name__ == "Action2Output"

    # Both should be subclasses of ActionOutput
    assert issubclass(result1, ActionOutput)
    assert issubclass(result2, ActionOutput)


def test_parse_parameters_with_complex_params():
    """Test parse_parameters with complex parameter structure."""
    complex_params = {
        "param1": {
            "data_type": "string",
            "required": True,
            "description": "First parameter",
            "order": 0,
        },
        "param2": {
            "data_type": "numeric",
            "required": False,
            "description": "Second parameter",
            "default": 42,
            "order": 1,
        },
        "param3": {
            "data_type": "boolean",
            "required": True,
            "description": "Third parameter",
            "order": 2,
        },
        "param4": {
            "data_type": "ph",
            "required": False,
            "description": "Placeholder parameter",
            "order": 3,
        },
    }

    result = ActionDeserializer.parse_parameters("complex_action", complex_params)

    # Should create a dynamic subclass, not the base Params class
    assert result != Params
    assert issubclass(result, Params)
    assert result.__name__ == "ComplexActionParams"

    # Should have the correct field annotations
    assert hasattr(result, "__annotations__")
    assert "param1" in result.__annotations__
    assert "param2" in result.__annotations__
    assert "param3" in result.__annotations__


def test_complex_output_specification():
    """Test parse_output with complex output specifications."""

    class NestedData(ActionOutput):
        deeply_nested: str

    class ComplexActionUser(ActionOutput):
        name: str
        contrived: list[list[str]]

    class ErrorMessage(ActionOutput):
        code: int
        message: str

    class ComplexActionDetails(ActionOutput):
        message: str
        error: ErrorMessage
        total: float
        users: list[ComplexActionUser]
        stupid_nested: list[list[list[list[list[NestedData]]]]]

    class ComplexActionOutput(ActionOutput):
        result: str
        details: list[ComplexActionDetails]

    complex_output_def = OutputsSerializer.serialize_datapaths(
        Params, ComplexActionOutput
    )

    raw_output = {
        "result": "success",
        "details": [
            {
                "message": "Operation completed",
                "error": {"code": 0, "message": "No error"},
                "total": 100.0,
                "users": [
                    {"name": "user1", "contrived": [["a", "b", "c"], ["d", "e", "f"]]},
                    {"name": "user2", "contrived": []},
                ],
                "stupid_nested": [[[[[{"deeply_nested": "value"}]]]]],
            },
            {
                "message": "Another operation",
                "error": {"code": 0, "message": "No error"},
                "total": 200.0,
                "users": [{"name": "user3", "contrived": [[]]}],
                "stupid_nested": [[[[[{"deeply_nested": "value"}]]]]],
            },
        ],
    }
    expected_output = ComplexActionOutput.parse_obj(raw_output)

    ParsedComplexActionOutput = ActionDeserializer.parse_output(
        "complex_action", complex_output_def
    )
    actual_output = ParsedComplexActionOutput.parse_obj(raw_output)

    assert actual_output == expected_output
