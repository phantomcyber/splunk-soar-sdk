from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from soar_sdk.views.template_filters import setup_jinja_env
from soar_sdk.paths import SDK_TEMPLATES


# Only Jinja2 is supported (Django is not used in the SDK now)
DEFAULT_TEMPLATE_ENGINE = "jinja"

# Base template for rendered HTML content (from platform perspective)
BASE_TEMPLATE_PATH = "templates/base/base_template.html"

# Error template for rendering error messages
ERROR_TEMPLATE_PATH = "base/error.html"


# Keeping abstract if for whatever reason we end up needing to support another template engine (like Django) in the future
class TemplateRenderer(ABC):
    """Abstract base class for template rendering engines."""

    def __init__(self, templates_dir: str) -> None:
        self.templates_dir = templates_dir

    @abstractmethod
    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with the given context."""
        pass

    @abstractmethod
    def render_error_template(
        self,
        error_type: str,
        error_message: str,
        function_name: str,
        template_name: str,
    ) -> str:
        """Render an error template with error information."""
        pass


class JinjaTemplateRenderer(TemplateRenderer):
    """Jinja2 template engine implementation."""

    def __init__(self, templates_dir: str) -> None:
        super().__init__(templates_dir)
        self._setup_jinja()

    def _setup_jinja(self) -> None:
        template_dirs = [self.templates_dir, str(SDK_TEMPLATES)]

        self.env = Environment(
            loader=FileSystemLoader(template_dirs),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=select_autoescape(["html"]),
        )

        setup_jinja_env(self.env)

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_error_template(
        self,
        error_type: str,
        error_message: str,
        function_name: str,
        template_name: str,
    ) -> str:
        try:
            template = self.env.get_template(ERROR_TEMPLATE_PATH)

            return template.render(
                widget_type="error",
                error_type=error_type,
                error_message=error_message,
                function_name=function_name,
                template_name=template_name,
                templates_dir=self.templates_dir,
            )
        except Exception:
            # Fallback to a simple error message if template rendering fails so can still see something on the UI
            return f"<div>Error in view function: {error_message}</div>"


def get_template_renderer(
    engine: Optional[str] = None, templates_dir: Optional[str] = None
) -> TemplateRenderer:
    if engine is None:
        engine = DEFAULT_TEMPLATE_ENGINE

    if templates_dir is None:
        templates_dir = str(Path.cwd() / "templates")

    if engine.lower() == "jinja":
        return JinjaTemplateRenderer(templates_dir)
    else:
        raise ValueError(f"Unsupported template engine: {engine}")


def get_templates_dir(function_globals: dict[str, Any]) -> str:
    caller_file = function_globals.get("__file__")
    if caller_file:
        app_dir = Path(caller_file).parent

        # Walk up the directory tree looking for a templates directory
        for current_dir in [app_dir, *list(app_dir.parents)]:
            templates_dir = current_dir / "templates"
            if templates_dir.exists() and templates_dir.is_dir():
                return str(templates_dir)

        # If no templates directory found, default to the app_dir level
        return str(app_dir.parent / "templates")

    return str(Path.cwd() / "templates")
