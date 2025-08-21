import pytest
from unittest import mock
from pathlib import Path
import tempfile
from jinja2 import TemplateNotFound

from soar_sdk.views.template_renderer import (
    JinjaTemplateRenderer,
    get_template_renderer,
    get_templates_dir,
    ERROR_TEMPLATE_PATH,
)


def test_jinja_template_renderer_init_sets_templates_dir():
    renderer = JinjaTemplateRenderer("test_templates")
    assert renderer.templates_dir == "test_templates"


def test_jinja_template_renderer_setup_jinja_has_custom_filters():
    renderer = JinjaTemplateRenderer("test_templates")
    assert "widget_uuid" in renderer.env.globals
    assert "human_datetime" in renderer.env.filters


def test_jinja_template_renderer_render_template_success():
    with tempfile.TemporaryDirectory() as temp_dir:
        template_path = Path(temp_dir) / "test.html"
        template_path.write_text("<h1>{{ title }}</h1>")

        renderer = JinjaTemplateRenderer(temp_dir)
        result = renderer.render_template("test.html", {"title": "Test Title"})

        assert result == "<h1>Test Title</h1>"


def test_jinja_template_renderer_render_template_not_found():
    renderer = JinjaTemplateRenderer("nonexistent_dir")

    with pytest.raises(TemplateNotFound):
        renderer.render_template("nonexistent.html", {})


def test_jinja_template_renderer_render_error_template_success():
    renderer = JinjaTemplateRenderer("test_templates")

    with mock.patch.object(renderer.env, "get_template") as mock_get_template:
        mock_template = mock.Mock()
        mock_template.render.return_value = "<div>Error: test error</div>"
        mock_get_template.return_value = mock_template

        result = renderer.render_error_template(
            "ValueError", "test error", "test_function", "test.html"
        )

        assert result == "<div>Error: test error</div>"
        mock_get_template.assert_called_once_with(ERROR_TEMPLATE_PATH)


def test_jinja_template_renderer_render_error_template_fallback():
    renderer = JinjaTemplateRenderer("test_templates")

    with mock.patch.object(
        renderer.env, "get_template", side_effect=Exception("Template error")
    ):
        result = renderer.render_error_template(
            "ValueError", "test error", "test_function", "test.html"
        )

        assert result == "<div>Error in view function: test error</div>"


def test_get_template_renderer_default_engine():
    renderer = get_template_renderer()
    assert isinstance(renderer, JinjaTemplateRenderer)


def test_get_template_renderer_unsupported_engine():
    with pytest.raises(ValueError, match="Unsupported template engine: django"):
        get_template_renderer(engine="django")


def test_get_template_renderer_custom_templates_dir():
    custom_dir = "/custom/templates"
    renderer = get_template_renderer(templates_dir=custom_dir)
    assert renderer.templates_dir == custom_dir


def test_get_templates_dir_with_file_path():
    function_globals = {"__file__": "/path/to/app/src/module.py"}
    result = get_templates_dir(function_globals)
    expected = str(Path("/path/to/app/src/module.py").parent.parent / "templates")
    assert result == expected


def test_get_templates_dir_without_file_path():
    function_globals = {}
    result = get_templates_dir(function_globals)
    expected = str(Path.cwd() / "templates")
    assert result == expected


def test_get_templates_dir_fallback_when_no_templates_found():
    with tempfile.TemporaryDirectory() as temp_dir:
        nested_path = Path(temp_dir) / "app" / "src" / "actions"
        nested_path.mkdir(parents=True)

        module_file = nested_path / "my_module.py"
        module_file.write_text("# fake module")

        function_globals = {"__file__": str(module_file)}

        result = get_templates_dir(function_globals)

        expected = str(nested_path.parent / "templates")
        assert result == expected


def test_get_templates_dir_finds_existing_templates_directory():
    with tempfile.TemporaryDirectory() as temp_dir:
        app_root = Path(temp_dir) / "app"
        templates_dir = app_root / "templates"
        nested_path = app_root / "src" / "actions"

        app_root.mkdir()
        templates_dir.mkdir()
        nested_path.mkdir(parents=True)

        module_file = nested_path / "my_module.py"
        module_file.write_text("# fake module")

        function_globals = {"__file__": str(module_file)}

        result = get_templates_dir(function_globals)

        assert result == str(templates_dir)
