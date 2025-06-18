from unittest import mock
import pytest
from soar_sdk.app import App
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.params import Params
from soar_sdk.views.components.pie_chart import PieChartData
from pydantic import BaseModel


class SampleViewOutput(ActionOutput):
    message: str
    count: int
    items: list[str] = OutputField(example_values=["item1", "item2"])


class ComplexViewOutput(ActionOutput):
    name: str
    data: dict


class SampleComponentData(BaseModel):
    title: str
    value: int
    enabled: bool


class InvalidComponentData:
    def __init__(self, data: str):
        self.data = data

    def dict(self):
        return {"data": self.data}


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


def test_view_handler_template_wrapper_functionality(simple_app: App):
    """Test that template wrapper correctly processes arguments and context."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message, "count": outputs[0].count}

    # Mock context and action results
    mock_context = {
        "accepts_prerender": False,
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"total_objects": 1, "total_objects_successful": 1},
            [
                mock.Mock(
                    get_data=lambda: [
                        {
                            "message": "test_msg",
                            "count": 5,
                            "items": ["a", "b"],
                        }
                    ]
                )
            ],
        )
    ]

    with (
        mock.patch(
            "soar_sdk.decorators.view_handler.get_templates_dir"
        ) as mock_get_dir,
        mock.patch(
            "soar_sdk.decorators.view_handler.get_template_renderer"
        ) as mock_get_renderer,
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
    mock_context = {
        "accepts_prerender": True,
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"total_objects": 1, "total_objects_successful": 1},
            [
                mock.Mock(
                    get_data=lambda: [
                        {"message": "test_msg", "count": 1, "items": ["x"]}
                    ]
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.decorators.view_handler.get_templates_dir"),
        mock.patch(
            "soar_sdk.decorators.view_handler.get_template_renderer"
        ) as mock_get_renderer,
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

    @simple_app.view_handler()
    def test_view(outputs: list[SampleViewOutput]) -> str:
        return f"<div>{outputs[0].message}</div>"

    mock_context = {
        "accepts_prerender": True,
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"total_objects": 1, "total_objects_successful": 1},
            [
                mock.Mock(
                    get_data=lambda: [
                        {"message": "test_msg", "count": 1, "items": ["x"]}
                    ]
                )
            ],
        )
    ]

    result = test_view(mock_action, mock_app_runs, mock_context)

    assert result == "<div>test_msg</div>"
    assert mock_context["prerender"] is True


def test_view_handler_error_handling_invalid_return_type(simple_app: App):
    """Test view_handler error handling for invalid return types."""

    with pytest.raises(TypeError, match="must return dict"):

        @simple_app.view_handler(template="test_template.html")
        def test_view(outputs: list[SampleViewOutput]) -> int:  # Invalid return type
            return 123


def test_view_handler_error_handling_invalid_return_type_with_prerender(
    simple_app: App,
):
    """Test view_handler error handling for invalid return types with prerender support."""

    with pytest.raises(TypeError, match="must return dict"):

        @simple_app.view_handler(template="test_template.html")
        def test_view(outputs: list[SampleViewOutput]) -> int:  # Invalid return type
            return 123


def test_view_handler_error_handling_template_render_failure(simple_app: App):
    """Test view_handler error handling when template rendering fails."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    mock_context = {
        "accepts_prerender": False,
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"total_objects": 1, "total_objects_successful": 1},
            [
                mock.Mock(
                    get_data=lambda: [
                        {"message": "test_msg", "count": 1, "items": ["x"]}
                    ]
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.decorators.view_handler.get_templates_dir"),
        mock.patch(
            "soar_sdk.decorators.view_handler.get_template_renderer"
        ) as mock_get_renderer,
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

    mock_context = {
        "accepts_prerender": False,
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"total_objects": 1, "total_objects_successful": 1},
            [
                mock.Mock(
                    get_data=lambda: [
                        {"message": "test_msg", "count": 1, "items": ["x"]}
                    ]
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.decorators.view_handler.get_templates_dir"),
        mock.patch(
            "soar_sdk.decorators.view_handler.get_template_renderer"
        ) as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_error_template.return_value = "<div>General Error</div>"
        mock_get_renderer.return_value = mock_renderer

        result = test_view(mock_action, mock_app_runs, mock_context)

        # Should catch exception and render error template
        mock_renderer.render_error_template.assert_called_once()
        assert result == "templates/base/base_template.html"


def test_view_handler_context_validation_error(simple_app: App):
    """Test view_handler raises error when context dict is missing."""

    @simple_app.view_handler(template="test_template.html")
    def test_view(outputs: list[SampleViewOutput]) -> dict:
        return {"message": outputs[0].message}

    # Missing context (third argument)
    mock_action = mock.Mock()
    mock_app_runs = []

    with pytest.raises(
        TypeError, match="missing 1 required positional argument: 'context'"
    ):
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

    with pytest.raises(AttributeError, match="'str' object has no attribute 'get'"):
        test_view(mock_action, mock_app_runs, mock_context)


def test_view_handler_integration_with_action_decorator(simple_app: App):
    """Test that view handlers work correctly when assigned to action view_handler."""

    @simple_app.view_handler(template="integration_test.html")
    def integration_view(outputs: list[SampleViewOutput]) -> dict:
        return {"processed_message": f"Processed: {outputs[0].message}"}

    @simple_app.action(view_handler=integration_view)
    def integration_action(params: Params) -> SampleViewOutput:
        return SampleViewOutput(message="test", count=1, items=["test"])

    # Verify the action was registered with the custom view
    actions = simple_app.get_actions()
    assert "integration_action" in actions
    assert actions["integration_action"].meta.view_handler == integration_view


def test_view_handler_component_functionality(simple_app: App):
    """Test view_handler with component parameter functionality."""

    @simple_app.view_handler()
    def test_component_view(outputs: list[SampleViewOutput]) -> PieChartData:
        return PieChartData(
            title=f"Component: {outputs[0].message}",
            labels=["Data"],
            values=[outputs[0].count],
            colors=["#FF6384"],
        )

    mock_context = {
        "accepts_prerender": False,
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"total_objects": 1, "total_objects_successful": 1},
            [
                mock.Mock(
                    get_data=lambda: [
                        {"message": "test_msg", "count": 5, "items": ["a"]}
                    ]
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.decorators.view_handler.get_templates_dir"),
        mock.patch(
            "soar_sdk.decorators.view_handler.get_template_renderer"
        ) as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_template.return_value = "<div>Component rendered</div>"
        mock_get_renderer.return_value = mock_renderer

        result = test_component_view(mock_action, mock_app_runs, mock_context)

        # Should render component template
        mock_renderer.render_template.assert_called_once_with(
            "components/pie_chart.html",
            {
                "accepts_prerender": False,
                "QS": {},
                "container": 1,
                "app": 2,
                "no_connection": False,
                "google_maps_key": False,
                "title": "Component: test_msg",
                "labels": ["Data"],
                "values": [5],
                "colors": ["#FF6384"],
            },
        )
        assert result == "templates/base/base_template.html"
        assert mock_context["html_content"] == "<div>Component rendered</div>"


def test_view_handler_component_with_prerender(simple_app: App):
    """Test view_handler component with prerender support."""

    @simple_app.view_handler()
    def test_component_view(outputs: list[SampleViewOutput]) -> PieChartData:
        return PieChartData(
            title="Prerender Test", labels=["Test"], values=[42], colors=["#36A2EB"]
        )

    mock_context = {
        "accepts_prerender": True,
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"total_objects": 1, "total_objects_successful": 1},
            [
                mock.Mock(
                    get_data=lambda: [{"message": "test", "count": 1, "items": ["x"]}]
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.decorators.view_handler.get_templates_dir"),
        mock.patch(
            "soar_sdk.decorators.view_handler.get_template_renderer"
        ) as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_template.return_value = "<div>Prerendered component</div>"
        mock_get_renderer.return_value = mock_renderer

        result = test_component_view(mock_action, mock_app_runs, mock_context)

        # Should return HTML directly for prerender
        assert result == "<div>Prerendered component</div>"
        assert mock_context["prerender"] is True


def test_view_handler_component_render_failure(simple_app: App):
    """Test view_handler component error handling when component rendering fails."""

    @simple_app.view_handler()
    def test_component_view(outputs: list[SampleViewOutput]) -> PieChartData:
        return PieChartData(title="Test", labels=["A"], values=[1], colors=["red"])

    mock_context = {
        "accepts_prerender": False,
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"total_objects": 1, "total_objects_successful": 1},
            [
                mock.Mock(
                    get_data=lambda: [{"message": "test", "count": 1, "items": ["x"]}]
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.decorators.view_handler.get_templates_dir"),
        mock.patch(
            "soar_sdk.decorators.view_handler.get_template_renderer"
        ) as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_template.side_effect = Exception(
            "Component template not found"
        )
        mock_renderer.render_error_template.return_value = (
            "<div>Component Render Error</div>"
        )
        mock_get_renderer.return_value = mock_renderer

        result = test_component_view(mock_action, mock_app_runs, mock_context)

        # Should catch exception and render error template
        mock_renderer.render_error_template.assert_called_once_with(
            "Component Rendering Failed",
            "Failed to render component 'pie_chart': Component template not found",
            "test_component_view",
            "component 'pie_chart'",
        )
        assert result == "templates/base/base_template.html"
        assert mock_context["html_content"] == "<div>Component Render Error</div>"


def test_view_handler_component_general_exception(simple_app: App):
    """Test view_handler component error handling for general exceptions."""

    @simple_app.view_handler()
    def test_component_view(outputs: list[SampleViewOutput]) -> PieChartData:
        raise RuntimeError("Component function error")

    mock_context = {
        "accepts_prerender": False,
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }
    mock_action = mock.Mock()
    mock_app_runs = [
        (
            {"total_objects": 1, "total_objects_successful": 1},
            [
                mock.Mock(
                    get_data=lambda: [{"message": "test", "count": 1, "items": ["x"]}]
                )
            ],
        )
    ]

    with (
        mock.patch("soar_sdk.decorators.view_handler.get_templates_dir"),
        mock.patch(
            "soar_sdk.decorators.view_handler.get_template_renderer"
        ) as mock_get_renderer,
    ):
        mock_renderer = mock.Mock()
        mock_renderer.render_error_template.return_value = (
            "<div>Component Function Error</div>"
        )
        mock_get_renderer.return_value = mock_renderer

        result = test_component_view(mock_action, mock_app_runs, mock_context)

        # Should catch exception and render error template
        mock_renderer.render_error_template.assert_called_once_with(
            "Component Function Error",
            "Error in component function 'test_component_view': Component function error",
            "test_component_view",
            "pie_chart",
        )
        assert result == "templates/base/base_template.html"
        assert mock_context["html_content"] == "<div>Component Function Error</div>"


def test_view_handler_component_integration_with_action(simple_app: App):
    """Test that component view handlers work correctly when assigned to action view_handler."""

    @simple_app.view_handler()
    def integration_component_view(
        outputs: list[SampleViewOutput],
    ) -> PieChartData:
        return PieChartData(
            title=f"Action Integration: {outputs[0].message}",
            labels=["Count"],
            values=[outputs[0].count * 2],
            colors=["#FFCE56"],
        )

    @simple_app.action(view_handler=integration_component_view)
    def integration_component_action(params: Params) -> SampleViewOutput:
        return SampleViewOutput(message="integration", count=5, items=["test"])

    # Verify the action was registered with the custom component view
    actions = simple_app.get_actions()
    assert "integration_component_action" in actions
    assert (
        actions["integration_component_action"].meta.view_handler
        == integration_component_view
    )


def test_view_handler_signature_validation_insufficient_params(simple_app: App):
    """Test view_handler raises TypeError when function has no parameters."""

    with pytest.raises(TypeError, match="must accept at least 1 parameter"):

        @simple_app.view_handler(template="test.html")
        def test_view() -> dict:
            return {}


def test_view_handler_signature_validation_missing_return_annotation(simple_app: App):
    """Test view_handler raises TypeError when function has no return type annotation."""

    with pytest.raises(TypeError, match="must have a return type annotation"):

        @simple_app.view_handler(template="test.html")
        def test_view(outputs):
            return {}


def test_view_handler_signature_validation_template_invalid_return_type(
    simple_app: App,
):
    """Test view_handler raises TypeError when template function returns wrong type."""

    with pytest.raises(TypeError, match="must return dict"):

        @simple_app.view_handler(template="test.html")
        def test_view(outputs: list[SampleViewOutput]) -> int:
            return 123


def test_view_handler_signature_validation_no_template_no_component_invalid_return_type(
    simple_app: App,
):
    """Test view_handler raises TypeError when function with no template/component returns wrong type."""

    with pytest.raises(TypeError, match="has invalid return type"):

        @simple_app.view_handler()
        def test_view(outputs: list[SampleViewOutput]) -> dict:
            return {}
