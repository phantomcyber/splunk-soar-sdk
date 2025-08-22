import dataclasses
from typing import Optional, Union
import ast
from collections.abc import Iterator

from soar_sdk.code_renderers.renderer import AstRenderer
from soar_sdk.meta.datatypes import to_python_type


@dataclasses.dataclass
class AssetContext:
    """Context for rendering individual configuration keys of an Asset class."""

    name: str
    description: Optional[str]
    required: bool
    default: Union[str, int, float, bool, None]
    data_type: str
    value_list: Optional[list[str]]

    @property
    def is_str(self) -> bool:
        """Check if the type is a string.

        Returns:
            bool: True if the type is str, False otherwise.
        """
        return self.py_type == "str"

    @property
    def py_type(self) -> str:
        """Get the Python type of the asset field.

        Returns:
            type: The Python type of the asset field.
        """
        return to_python_type(self.data_type).__name__


class AssetRenderer(AstRenderer[list[AssetContext]]):
    """A class to render an app's Asset class using Jinja2 templates."""

    def render_ast(self) -> Iterator[ast.stmt]:
        """Render the Asset class by building an AST.

        Returns:
            str: The rendered code for the Asset class.
        """
        asset_class = ast.ClassDef(
            name="Asset",
            bases=[ast.Name(id="BaseAsset", ctx=ast.Load())],
            body=[],
            decorator_list=[],
            keywords=[],
        )

        for field in self.context:
            field_name = ast.Name(id=field.name, ctx=ast.Store())
            field_type = ast.Name(id=field.py_type, ctx=ast.Load())

            field_kwargs = [
                ast.keyword(arg="required", value=ast.Constant(value=field.required)),
            ]
            if field.description is not None:
                field_kwargs.append(
                    ast.keyword(
                        arg="description", value=ast.Constant(value=field.description)
                    )
                )
            if field.default is not None:
                if field.data_type == "timezone":
                    field_kwargs.append(
                        ast.keyword(
                            arg="default",
                            value=ast.Call(
                                func=ast.Name(id="ZoneInfo", ctx=ast.Load()),
                                args=[ast.Constant(value=field.default)],
                                keywords=[],
                            ),
                        )
                    )
                else:
                    field_kwargs.append(
                        ast.keyword(
                            arg="default",
                            value=ast.Constant(value=field.default),
                        )
                    )
            if field.value_list is not None:
                field_kwargs.append(
                    ast.keyword(
                        arg="value_list",
                        value=ast.List(
                            elts=[ast.Constant(value=v) for v in field.value_list]
                        ),
                    )
                )

            field_statement = ast.AnnAssign(
                target=field_name,
                annotation=field_type,
                simple=1,
                value=ast.Call(
                    func=ast.Name(id="AssetField", ctx=ast.Load()),
                    args=[],
                    keywords=field_kwargs,
                ),
            )
            asset_class.body.append(field_statement)

        if not asset_class.body:
            asset_class.body.append(ast.Pass())

        yield asset_class
