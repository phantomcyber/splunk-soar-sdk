import dataclasses

from soar_sdk.code_renderers.renderer import Renderer


@dataclasses.dataclass
class PreCommitConfigContext:
    """Model representing context required to render a pre-commit config."""

    private: bool = False

    def to_dict(self) -> dict:
        """Convert the context to a dictionary suitable for Jinja2 templating."""
        return dataclasses.asdict(self)


class PreCommitConfigRenderer(Renderer[PreCommitConfigContext]):
    """A class to render a .pre-commit-config.yaml file using Jinja2 templates."""

    def render(self) -> str:
        """Render the pre-commit config file using Jinja2."""
        template = self.jinja_env.get_template("pre-commit-config.yaml.jinja")
        return template.render(self.context.to_dict())
