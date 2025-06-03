from unittest import mock
import pytest
from soar_sdk.app import App
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.params import Params


class SampleViewOutput(ActionOutput):
    message: str
    count: int
    items: list[str] = OutputField(example_values=["item1", "item2"])


class ComplexViewOutput(ActionOutput):
    name: str
    data: dict


def test_view_handler_with_template_decoration(simple_app: App):
    """Test view_handler decorator with template parameter."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message, "count": outputs[0].count}

    assert callable(test_view)
    assert test_view.__name__ == "test_view"


def test_view_handler_without_template_decoration(simple_app: App):
    """Test view_handler decorator without template parameter."""

    @simple_app.view_handler()
    def test_view(outputs: list[SampleViewOutput]) -> str:
        return "<html><body>Straight HTML return</body></html>"

    assert callable(test_view)
    assert test_view.__name__ == "test_view"


def test_view_handler_with_output_class_parameter(simple_app: App):
    """Test view_handler decorator with explicit output_class parameter."""

    @simple_app.view_handler(
        template="test_template.html", output_class=SampleViewOutput
    )
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    assert callable(test_view)


def test_view_handler_template_wrapper_functionality(simple_app: App):
    """Test that template wrapper correctly processes arguments and context."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message, "count": outputs[0].count}

    # Mock context and action results
    mock_context = {"accepts_prerender": False}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {
                        "message": "test_msg",
                        "count": 5,
                        "items": ["a", "b"],
                    }
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.app.get_templates_dir") as mock_get_dir,
        mock.patch("soar_sdk.app.get_template_renderer") as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_template.return_value = "<html>rendered</html>"
        mock_get_renderer.return_value = mock_renderer
        mock_get_dir.return_value = "/mock/templates"

        result = test_view(mock_action, mock_app_runs, mock_context)

        # Should return the base template path for backwards compatibility
        assert result == "templates/base/base_template.html"
        assert mock_context["html_content"] == "<html>rendered</html>"


def test_view_handler_template_wrapper_prerender_support(simple_app: App):
    """Test that template wrapper handles prerender context correctly."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    # Mock context with prerender support
    mock_context = {"accepts_prerender": True}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {"message": "test_msg", "count": 1, "items": ["x"]}
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.app.get_templates_dir"),
        mock.patch("soar_sdk.app.get_template_renderer") as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_template.return_value = "<html>prerendered</html>"
        mock_get_renderer.return_value = mock_renderer

        result = test_view(mock_action, mock_app_runs, mock_context)

        # Should return HTML directly for prerender support
        assert result == "<html>prerendered</html>"
        assert mock_context["prerender"] is True


def test_view_handler_direct_html_return(simple_app: App):
    """Test view_handler when function returns HTML string directly."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> str:
        return f"<div>{outputs[0].message}</div>"

    mock_context = {"accepts_prerender": True}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {"message": "test_msg", "count": 1, "items": ["x"]}
                )
            ],
        )
    ]

    result = test_view(mock_action, mock_app_runs, mock_context)

    assert result == "<div>test_msg</div>"
    assert mock_context["prerender"] is True


def test_view_handler_error_handling_invalid_return_type(simple_app: App):
    """Test view_handler error handling for invalid return types."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> int:  # Invalid return type
        return 123

    mock_context = {"accepts_prerender": False}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {"message": "test_msg", "count": 1, "items": ["x"]}
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.app.get_templates_dir"),
        mock.patch("soar_sdk.app.get_template_renderer") as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_error_template.return_value = (
            "<div>Error: Invalid return type</div>"
        )
        mock_get_renderer.return_value = mock_renderer

        result = test_view(mock_action, mock_app_runs, mock_context)

        # Should render error template
        mock_renderer.render_error_template.assert_called_once()
        assert result == "templates/base/base_template.html"
        assert mock_context["html_content"] == "<div>Error: Invalid return type</div>"


def test_view_handler_error_handling_invalid_return_type_with_prerender(
    simple_app: App,
):
    """Test view_handler error handling for invalid return types with prerender support."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> int:  # Invalid return type
        return 123

    mock_context = {"accepts_prerender": True}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {"message": "test_msg", "count": 1, "items": ["x"]}
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.app.get_templates_dir"),
        mock.patch("soar_sdk.app.get_template_renderer") as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_error_template.return_value = (
            "<div>Error: Invalid return type with prerender</div>"
        )
        mock_get_renderer.return_value = mock_renderer

        result = test_view(mock_action, mock_app_runs, mock_context)

        # Should render error template and return HTML directly for prerender
        mock_renderer.render_error_template.assert_called_once()
        assert result == "<div>Error: Invalid return type with prerender</div>"
        assert mock_context["prerender"] is True


def test_view_handler_error_handling_template_render_failure(simple_app: App):
    """Test view_handler error handling when template rendering fails."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    mock_context = {"accepts_prerender": False}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {"message": "test_msg", "count": 1, "items": ["x"]}
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.app.get_templates_dir"),
        mock.patch("soar_sdk.app.get_template_renderer") as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_template.side_effect = Exception("Template error")
        mock_renderer.render_error_template.return_value = "<div>Template Error</div>"
        mock_get_renderer.return_value = mock_renderer

        result = test_view(mock_action, mock_app_runs, mock_context)

        # Should catch exception and render error template
        mock_renderer.render_error_template.assert_called_once()
        assert result == "templates/base/base_template.html"


def test_view_handler_error_handling_general_exception(simple_app: App):
    """Test view_handler error handling for general exceptions."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        raise ValueError("Something went wrong")

    mock_context = {"accepts_prerender": False}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {"message": "test_msg", "count": 1, "items": ["x"]}
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.app.get_templates_dir"),
        mock.patch("soar_sdk.app.get_template_renderer") as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_error_template.return_value = "<div>General Error</div>"
        mock_get_renderer.return_value = mock_renderer

        result = test_view(mock_action, mock_app_runs, mock_context)

        # Should catch exception and render error template
        mock_renderer.render_error_template.assert_called_once()
        assert result == "templates/base/base_template.html"


def test_view_handler_invalid_return_type_none(simple_app: App):
    """Test view_handler error handling for None return type via bypassing parser."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    mock_context = {"accepts_prerender": False}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {"message": "test_msg", "count": 1, "items": ["x"]}
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.app.get_templates_dir"),
        mock.patch("soar_sdk.app.get_template_renderer") as mock_get_renderer,
        mock.patch("soar_sdk.app.ViewFunctionParser") as mock_parser_class,
    ):
        mock_parser = mock.Mock()
        mock_parser.execute.return_value = (
            None  # Return None to trigger invalid type error
        )
        mock_parser_class.return_value = mock_parser

        mock_renderer = mock.Mock()
        mock_renderer.render_error_template.return_value = "<div>Error: NoneType</div>"
        mock_get_renderer.return_value = mock_renderer

        result = test_view(mock_action, mock_app_runs, mock_context)

        mock_renderer.render_error_template.assert_called_once_with(
            "Invalid Return Type",
            "View function returned NoneType, expected dict or str",
            "test_view",
            "test_template.html",
        )
        assert result == "templates/base/base_template.html"
        assert mock_context["html_content"] == "<div>Error: NoneType</div>"


def test_view_handler_context_validation_error(simple_app: App):
    """Test view_handler raises error when context dict is missing."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    # Missing context (third argument)
    mock_action = mock.Mock()
    mock_app_runs = []

    with pytest.raises(ValueError, match="View handler expected context dict"):
        test_view(mock_action, mock_app_runs)


def test_view_handler_context_validation_wrong_type(simple_app: App):
    """Test view_handler raises error when context is not a dict."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    # Context is not a dict
    mock_action = mock.Mock()
    mock_app_runs = []
    mock_context = "not_a_dict"

    with pytest.raises(ValueError, match="View handler expected context dict"):
        test_view(mock_action, mock_app_runs, mock_context)


def test_view_handler_without_template_returns_function(simple_app: App):
    """Test view_handler without template returns original function."""

    @simple_app.view_handler()
    def test_view(outputs: list[SampleViewOutput]) -> str:
        return "<html><body>Straight HTML return</body></html>"

    # Without template, should return the original function
    assert test_view.__name__ == "test_view"


def test_view_handler_with_component_parameter(simple_app: App):
    """Test view_handler decorator with component parameter (future functionality)."""

    @simple_app.view_handler(component="test_component")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    # Component parameter is TODO
    assert callable(test_view)


def test_view_handler_auto_output_detection(simple_app: App):
    """Test that view_handler auto-detects output class from function signature."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[ComplexViewOutput]) -> dict:
        return {"name": outputs[0].name, "data": outputs[0].data}

    mock_context = {"accepts_prerender": False}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {"name": "test_name", "data": {"key": "value"}}
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.app.get_templates_dir"),
        mock.patch("soar_sdk.app.get_template_renderer") as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_template.return_value = "<html>auto-detected</html>"
        mock_get_renderer.return_value = mock_renderer

        result = test_view(mock_action, mock_app_runs, mock_context)

        # Should work with auto-detected output class
        assert result == "templates/base/base_template.html"
        assert mock_context["html_content"] == "<html>auto-detected</html>"


def test_view_handler_explicit_output_class_override(simple_app: App):
    """Test view_handler with explicit output_class overrides function signature."""

    @simple_app.view_handler(
        template="test_template.html",
        output_class=SampleViewOutput,  # Different type in signature
    )
    def test_view(
        outputs: list[ComplexViewOutput],
    ) -> dict:
        return {"message": outputs[0].message, "count": outputs[0].count}

    mock_context = {"accepts_prerender": False}
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"app_id": "test"},
            [
                mock.Mock(
                    get_data=lambda: {
                        "message": "test_msg",
                        "count": 42,
                        "items": ["x", "y"],
                    }
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.app.get_templates_dir"),
        mock.patch("soar_sdk.app.get_template_renderer") as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_template.return_value = "<html>explicit-class</html>"
        mock_get_renderer.return_value = mock_renderer

        result = test_view(mock_action, mock_app_runs, mock_context)

        # Should use explicit output class
        assert result == "templates/base/base_template.html"
        assert mock_context["html_content"] == "<html>explicit-class</html>"


def test_view_handler_multiple_decorators_same_app(simple_app: App):
    """Test that multiple view_handler decorators can be used on the same app."""

    @simple_app.view_handler(template="template1.html")
    def view1(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    @simple_app.view_handler(template="template2.html")
    def view2(outputs: list[ComplexViewOutput]) -> dict:
        return {"name": outputs[0].name}

    # Both should be properly decorated
    assert callable(view1)
    assert callable(view2)
    assert view1.__name__ == "view1"
    assert view2.__name__ == "view2"


def test_view_handler_preserves_function_metadata(simple_app: App):
    """Test that view_handler preserves original function metadata."""

    @simple_app.view_handler(template="test_template.html")
    def test_view_function(outputs: list[SampleViewOutput]) -> dict:
        """This is a test view function."""
        return {"message": outputs[0].message}

    # Should preserve function name and docstring
    assert test_view_function.__name__ == "test_view_function"
    assert test_view_function.__doc__ == "This is a test view function."


def test_view_handler_integration_with_action_decorator(simple_app: App):
    """Test that view handlers work correctly when assigned to action custom_view."""

    @simple_app.view_handler(template="integration_test.html")
    def integration_view(outputs: list[SampleViewOutput]) -> dict:
        return {"processed_message": f"Processed: {outputs[0].message}"}

    @simple_app.action(custom_view=integration_view)
    def integration_action(params: Params) -> SampleViewOutput:
        return SampleViewOutput(message="test", count=1, items=["test"])

    # Verify the action was registered with the custom view
    actions = simple_app.get_actions()
    assert "integration_action" in actions
    assert actions["integration_action"].meta.custom_view == integration_view
