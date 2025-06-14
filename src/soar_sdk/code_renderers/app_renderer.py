import dataclasses

from soar_sdk.code_renderers.renderer import Renderer


@dataclasses.dataclass
class AppContext:
    name: str
    app_type: str
    logo: str
    logo_dark: str
    product_vendor: str
    product_name: str
    publisher: str
    appid: str
    fips_compliant: bool


class AppRenderer(Renderer[AppContext]):
    """
    A class to render an app.py file using Jinja2 templates.
    """

    def render(self) -> str:
        """
        Render the App class using Jinja2.

        Returns:
            str: The rendered content for the App class.
        """
        template = self.jinja_env.get_template("app.py.jinja")
        rendered_content = template.render(dataclasses.asdict(self.context))
        return rendered_content
