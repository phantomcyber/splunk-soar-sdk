import dataclasses

from soar_sdk.code_renderers.renderer import Renderer
from soar_sdk.compat import PythonVersion


@dataclasses.dataclass
class TomlContext:
    name: str
    version: str
    description: str
    copyright: str
    python_versions: list[PythonVersion]
    authors: list[str] = dataclasses.field(default_factory=list)
    dependencies: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:
        """
        Convert the TomlContext to a dictionary suitable for Jinja2 templating.

        Returns:
            dict: A dictionary representation of the TomlContext.
        """
        data = dataclasses.asdict(self)
        data.update(
            {
                "python_versions": [str(py) for py in self.python_versions],
                "requires_python": PythonVersion.to_requires_python(
                    self.python_versions
                ),
            }
        )
        return data


class TomlRenderer(Renderer[TomlContext]):
    """
    A class to render a pyproject.toml file using Jinja2 templates.
    """

    def render(self) -> str:
        """
        Render the pyproject.toml file using Jinja2.

        Returns:
            str: The rendered content for the pyproject.toml file.
        """
        template = self.jinja_env.get_template("pyproject.toml.jinja")
        rendered_content = template.render(self.context.to_dict())
        return rendered_content
