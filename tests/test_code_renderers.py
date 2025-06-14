import jinja2 as j2
from soar_sdk.code_renderers.renderer import Renderer
import pytest
from unittest.mock import Mock
from soar_sdk.code_renderers import app_renderer, toml_renderer
from soar_sdk.compat import PythonVersion


class ConcreteRenderer(Renderer[str]):
    """Concrete implementation of Renderer for testing purposes."""

    def render(self) -> str:
        return f"Rendered: {self.context}"


def test_init_with_default_jinja_env():
    """Test initialization with default Jinja2 environment."""
    context = "test_context"
    renderer = ConcreteRenderer(context)

    assert renderer.context == context
    assert isinstance(renderer.jinja_env, j2.Environment)
    assert renderer.render() == "Rendered: test_context"


def test_init_with_custom_jinja_env():
    """Test initialization with custom Jinja2 environment."""
    context = "test_context"
    custom_env = j2.Environment(loader=j2.DictLoader({}))
    renderer = ConcreteRenderer(context, custom_env)

    assert renderer.context == context
    assert renderer.jinja_env is custom_env
    assert renderer.render() == "Rendered: test_context"


@pytest.fixture
def mock_jinja_env():
    mock_env = Mock(spec=j2.Environment)
    mock_env.get_template.return_value.render.return_value = "Rendered content"
    return mock_env


def test_app_renderer(mock_jinja_env):
    context = app_renderer.AppContext(
        name="Test App",
        app_type="ingestion",
        logo="logo.png",
        logo_dark="logo_dark.png",
        product_vendor="Test Vendor",
        product_name="Test Product",
        publisher="Test Publisher",
        appid="test_app_123",
        fips_compliant=True,
    )

    renderer = app_renderer.AppRenderer(context, mock_jinja_env)
    rendered = renderer.render()
    mock_jinja_env.get_template.assert_called_once_with("app.py.jinja")
    assert rendered == "Rendered content"


def test_toml_renderer(mock_jinja_env):
    context = toml_renderer.TomlContext(
        name="Test App",
        version="1.0.0",
        description="A test application",
        copyright="2023 Test Company",
        python_versions=PythonVersion.all(),
    )

    context_dict = context.to_dict()
    assert context_dict["requires_python"] == PythonVersion.to_requires_python(
        context.python_versions
    )
    assert [str(py) for py in PythonVersion.all()] == context_dict["python_versions"]

    renderer = toml_renderer.TomlRenderer(context, mock_jinja_env)
    rendered = renderer.render()
    mock_jinja_env.get_template.assert_called_once_with("pyproject.toml.jinja")
    assert rendered == "Rendered content"
