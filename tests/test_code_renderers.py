import jinja2 as j2
from soar_sdk.code_renderers.renderer import Renderer
import pytest
from unittest.mock import Mock
from soar_sdk.code_renderers import (
    app_renderer,
    toml_renderer,
    asset_renderer,
)
from soar_sdk.compat import PythonVersion
import ast


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


def test_app_renderer():
    context = app_renderer.AppContext(
        name="test_app",
        app_type="ingestion",
        logo="logo.png",
        logo_dark="logo_dark.png",
        product_vendor="Test Vendor",
        product_name="Test Product",
        publisher="Test Publisher",
        appid="test_app_123",
        fips_compliant=True,
        app_content=[
            ast.ClassDef(
                name="Asset",
                bases=[ast.Name(id="BaseAsset", ctx=ast.Load())],
                body=[ast.Pass()],
                decorator_list=[],
            ),
        ],
    )

    renderer = app_renderer.AppRenderer(context)
    rendered = renderer.render()

    classes = [
        statement for statement in rendered.body if isinstance(statement, ast.ClassDef)
    ]
    class_names = set(cls.name for cls in classes)
    assert class_names == {"Asset"}

    assignments = [
        statement for statement in rendered.body if isinstance(statement, ast.Assign)
    ]
    assignment_names = set(
        target.id
        for assign in assignments
        for target in assign.targets
        if isinstance(target, ast.Name)
    )
    assert assignment_names == {"logger", "app"}

    main_check = next(
        (stmt for stmt in rendered.body if isinstance(stmt, ast.If)), None
    )
    assert main_check is not None


def test_toml_renderer(mock_jinja_env):
    context = toml_renderer.TomlContext(
        name="test_app",
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


@pytest.mark.parametrize(
    ("data_type", "is_str", "py_type"),
    (
        ("string", True, "str"),
        ("password", True, "str"),
        ("numeric", False, "float"),
        ("boolean", False, "bool"),
    ),
)
def test_asset_context_properties(data_type: str, is_str: bool, py_type: str):
    """Test AssetContext properties."""
    context = asset_renderer.AssetContext(
        name="test_field",
        description="Test field description",
        required=True,
        default="default_value",
        data_type=data_type,
        value_list=["option1", "option2"],
    )

    assert context.is_str is is_str
    assert context.py_type == py_type


def test_asset_renderer():
    """Test AssetRenderer with asset fields context."""
    asset_fields = [
        asset_renderer.AssetContext(
            name="username",
            description="Username for authentication",
            required=True,
            default=None,
            data_type="string",
            value_list=None,
        ),
        asset_renderer.AssetContext(
            name="port",
            description="Port number",
            required=False,
            default=443,
            data_type="numeric",
            value_list=None,
        ),
    ]

    renderer = asset_renderer.AssetRenderer(asset_fields)
    rendered = renderer.render_ast()
    asset_class = next(rendered)

    expected_output = "\n".join(
        [
            "class Asset(BaseAsset):",
            "    username: str = AssetField(required=True, description='Username for authentication')",
            "    port: float = AssetField(required=False, description='Port number', default=443)",
        ]
    )

    assert ast.unparse(asset_class) == expected_output
