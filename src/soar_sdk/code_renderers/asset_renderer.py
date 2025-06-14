import dataclasses
from typing import Optional, Union

from soar_sdk.code_renderers.renderer import Renderer
from soar_sdk.meta.datatypes import to_python_type


@dataclasses.dataclass
class AssetContext:
    """
    Context for rendering individual configuration keys of an Asset class.
    """

    name: str
    description: Optional[str]
    required: bool
    default: Union[str, int, float, bool, None]
    data_type: str
    value_list: Optional[list[str]]

    @property
    def is_str(self) -> bool:
        """
        Check if the type is a string.

        Returns:
            bool: True if the type is str, False otherwise.
        """
        return self.py_type == "str"

    @property
    def py_type(self) -> str:
        """
        Get the Python type of the asset field.

        Returns:
            type: The Python type of the asset field.
        """
        return to_python_type(self.data_type).__name__


class AssetRenderer(Renderer[list[AssetContext]]):
    """
    A class to render an app's Asset class using Jinja2 templates.
    """

    def render(self) -> str:
        """
        Render the Asset class using Jinja2.

        Returns:
            str: The rendered code for the Asset class.
        """
        template = self.jinja_env.get_template("asset.py.jinja")
        rendered_content = template.render(asset_fields=self.context)
        return rendered_content
