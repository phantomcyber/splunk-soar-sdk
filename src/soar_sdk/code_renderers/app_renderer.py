import dataclasses
import ast
from typing import Union
from collections.abc import Iterator


def create_default_asset_cls() -> ast.ClassDef:
    """
    Create a default Asset class definition.

    Returns:
        ast.ClassDef: The AST node representing the Asset class.
    """
    return ast.ClassDef(
        name="Asset",
        bases=[ast.Name(id="BaseAsset", ctx=ast.Load())],
        body=[ast.Pass()],
        decorator_list=[],
        keywords=[],
    )


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
    app_content: list[ast.stmt] = dataclasses.field(default_factory=list)
    asset_cls: ast.ClassDef = dataclasses.field(
        default_factory=create_default_asset_cls
    )


class AppRenderer:
    """
    A class to render an app.py module using ASTs.
    """

    def __init__(self, context: AppContext) -> None:
        """
        Initialize the AppRenderer with the given context.

        Args:
            context (AppContext): The context containing app details.
        """
        self.context = context

    @staticmethod
    def create_default_imports() -> Iterator[Union[ast.Import, ast.ImportFrom]]:
        """
        Create default imports for the App module.

        Returns:
            Iterator[ast.Import]: An iterator of Import nodes.
        """
        yield ast.ImportFrom(
            module="typing", names=[ast.alias(name="Union", asname=None)], level=0
        )
        yield ast.ImportFrom(
            module="collections.abc",
            names=[ast.alias(name="Iterator", asname=None)],
            level=0,
        )
        yield ast.ImportFrom(
            module="soar_sdk.abstract",
            names=[ast.alias(name="SOARClient", asname=None)],
            level=0,
        )
        yield ast.ImportFrom(
            module="soar_sdk.app", names=[ast.alias(name="App", asname=None)], level=0
        )
        yield ast.ImportFrom(
            module="soar_sdk.params",
            names=[
                ast.alias(name="Param", asname=None),
                ast.alias(name="Params", asname=None),
                ast.alias(name="OnPollParams", asname=None),
            ],
            level=0,
        )
        yield ast.ImportFrom(
            module="soar_sdk.action_results",
            names=[
                ast.alias(name="ActionOutput", asname=None),
                ast.alias(name="OutputField", asname=None),
            ],
            level=0,
        )
        yield ast.ImportFrom(
            module="soar_sdk.asset",
            names=[
                ast.alias(name="BaseAsset", asname=None),
                ast.alias(name="AssetField", asname=None),
            ],
            level=0,
        )
        yield ast.ImportFrom(
            module="soar_sdk.logging",
            names=[ast.alias(name="getLogger", asname=None)],
            level=0,
        )
        yield ast.ImportFrom(
            module="soar_sdk.models.container",
            names=[ast.alias(name="Container", asname=None)],
            level=0,
        )
        yield ast.ImportFrom(
            module="soar_sdk.models.artifact",
            names=[ast.alias(name="Artifact", asname=None)],
            level=0,
        )

    def create_app_constructor(self) -> ast.Assign:
        """
        Create the App class constructor.

        Returns:
            ast.Assign: The AST node representing the App class instantiation.
        """
        return ast.Assign(
            targets=[ast.Name(id="app", ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id="App", ctx=ast.Load()),
                args=[],
                keywords=[
                    ast.keyword(
                        arg="name", value=ast.Constant(value=self.context.name)
                    ),
                    ast.keyword(
                        arg="app_type", value=ast.Constant(value=self.context.app_type)
                    ),
                    ast.keyword(
                        arg="logo", value=ast.Constant(value=self.context.logo)
                    ),
                    ast.keyword(
                        arg="logo_dark",
                        value=ast.Constant(value=self.context.logo_dark),
                    ),
                    ast.keyword(
                        arg="product_vendor",
                        value=ast.Constant(value=self.context.product_vendor),
                    ),
                    ast.keyword(
                        arg="product_name",
                        value=ast.Constant(value=self.context.product_name),
                    ),
                    ast.keyword(
                        arg="publisher",
                        value=ast.Constant(value=self.context.publisher),
                    ),
                    ast.keyword(
                        arg="appid", value=ast.Constant(value=self.context.appid)
                    ),
                    ast.keyword(
                        arg="fips_compliant",
                        value=ast.Constant(value=self.context.fips_compliant),
                    ),
                    ast.keyword(
                        arg="asset_cls",
                        value=ast.Name(id=self.context.asset_cls.name, ctx=ast.Load()),
                    ),
                ],
            ),
        )

    @staticmethod
    def create_main_check() -> ast.If:
        """
        Create the main check for the App module.

        Returns:
            ast.If: The AST node representing the main check.
        """
        return ast.If(
            test=ast.Compare(
                ast.Name(id="__name__", ctx=ast.Load()),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value="__main__")],
            ),
            body=[
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="app", ctx=ast.Load()),
                            attr="cli",
                            ctx=ast.Load(),
                        ),
                        args=[],
                        keywords=[],
                    )
                )
            ],
            orelse=[],
        )

    def render(self) -> ast.Module:
        """
        Render the App module.

        Returns:
            ast.module: The rendered content for the App class.
        """
        app_module = ast.Module(body=[], type_ignores=[])

        for import_node in self.create_default_imports():
            app_module.body.append(import_node)

        app_module.body.append(
            ast.Assign(
                targets=[ast.Name(id="logger", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="getLogger", ctx=ast.Load()), args=[], keywords=[]
                ),
            )
        )

        app_module.body.append(self.context.asset_cls)

        app_module.body.append(self.create_app_constructor())

        for content in self.context.app_content:
            app_module.body.append(content)

        app_module.body.append(self.create_main_check())

        return app_module
