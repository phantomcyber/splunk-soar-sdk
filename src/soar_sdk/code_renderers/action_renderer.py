import textwrap
from typing import ClassVar, Optional
from collections.abc import Iterator
import typing
import ast
from pydantic.fields import Undefined

from soar_sdk.action_results import ActionOutput
from soar_sdk.cli.utils import normalize_field_name
from soar_sdk.code_renderers.renderer import Renderer
from soar_sdk.meta.actions import ActionMeta


class ActionRenderer(Renderer[ActionMeta]):
    """
    Generates code for actions in the Soar SDK.
    """

    # These actions are the same for all apps, so we use stubs instead of templates.
    STUBS: ClassVar[dict[str, str]] = {
        "on poll": textwrap.dedent(
            """
            @app.on_poll()
            def on_poll(
                soar: SOARClient, asset: Asset, params: OnPollParams
            ) -> Iterator[Union[Container, Artifact]]:
                raise NotImplementedError()
            """
        ),
        "test connectivity": textwrap.dedent(
            """
            @app.test_connectivity()
            def test_connectivity(soar: SOARClient, asset: Asset) -> None:
                raise NotImplementedError()
            """
        ),
    }

    AST_STUBS: ClassVar[dict[str, ast.FunctionDef]] = {
        "test connectivity": ast.FunctionDef(
            name="test_connectivity",
            args=ast.arguments(
                args=[
                    ast.arg(arg="soar", annotation=ast.Name(id="SOARClient")),
                    ast.arg(arg="asset", annotation=ast.Name(id="Asset")),
                ],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            returns=ast.Name(id="None", ctx=ast.Load()),
            body=[
                ast.Raise(
                    ast.Call(
                        func=ast.Name(id="NotImplementedError"), args=[], keywords=[]
                    )
                )
            ],
            decorator_list=[
                ast.Call(
                    func=ast.Name(id="app.test_connectivity", ctx=ast.Load()),
                )
            ],
        ),
        "on poll": ast.FunctionDef(
            name="on_poll",
            args=ast.arguments(
                args=[
                    ast.arg(arg="soar", annotation=ast.Name(id="SOARClient")),
                    ast.arg(arg="asset", annotation=ast.Name(id="Asset")),
                    ast.arg(arg="params", annotation=ast.Name(id="OnPollParams")),
                ],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=[
                ast.Raise(
                    ast.Call(
                        func=ast.Name(id="NotImplementedError"), args=[], keywords=[]
                    )
                )
            ],
            decorator_list=[
                ast.Call(
                    func=ast.Name(id="app.on_poll", ctx=ast.Load()),
                    args=[],
                )
            ],
            returns=ast.Subscript(
                value=ast.Name(id="Iterator", ctx=ast.Load()),
                slice=ast.Subscript(
                    value=ast.Name(id="Union", ctx=ast.Load()),
                    slice=ast.Tuple(
                        elts=[
                            ast.Name(id="Container", ctx=ast.Load()),
                            ast.Name(id="Artifact", ctx=ast.Load()),
                        ],
                        ctx=ast.Load(),
                    ),
                    ctx=ast.Load(),
                ),
                ctx=ast.Load(),
            ),
        ),
    }

    @property
    def action_meta(self) -> ActionMeta:
        """
        Returns the action metadata.
        Returns:
            ActionMeta: The metadata for the action.
        """
        return self.context

    def render(self) -> str:
        """
        Generates the code for the action.
        Returns:
            str: The rendered code for the action.
        """
        # Reserved actions have stubs, not templates.
        if (stub := self.STUBS.get(self.action_meta.action)) is not None:
            return stub

        return self.jinja_env.get_template("action.py.jinja").render(
            meta=self.action_meta,
            params=list(self.render_parameters()),
            params_class_name=self.action_meta.parameters.__name__,
            outputs=list(self.render_outputs()),
            outputs_class_name=self.action_meta.output.__name__,
        )

    def render_ast(self) -> Iterator[ast.AST]:
        """
        Generates the AST for the action.
        Returns:
            Iterator[ast.AST]: An iterator of AST nodes representing the action, its parameters, and its outputs.
        """
        # Reserved actions have stubs, not templates.
        if (stub := self.AST_STUBS.get(self.action_meta.action)) is not None:
            yield ast.fix_missing_locations(stub)
            return

        yield self.render_params_ast()

        outputs = list(self.render_outputs_ast())
        yield from iter(outputs)

        return_type = (
            ast.Name(id=self.action_meta.output.__name__, ctx=ast.Load())
            if outputs
            else ast.Name(id="ActionOutput", ctx=ast.Load())
        )

        decorator_keywords = [
            ast.keyword(
                arg="description",
                value=ast.Constant(value=self.action_meta.description),
            ),
            ast.keyword(
                arg="action_type",
                value=ast.Constant(value=self.action_meta.type),
            ),
        ]
        if not self.action_meta.read_only:
            decorator_keywords.append(
                ast.keyword(
                    arg="read_only",
                    value=ast.Constant(value=self.action_meta.read_only),
                )
            )
        if self.action_meta.verbose:
            decorator_keywords.append(
                ast.keyword(
                    arg="verbose",
                    value=ast.Constant(
                        value=self.action_meta.verbose.replace('"', '\\"')
                    ),
                )
            )

        node = ast.FunctionDef(
            name=self.action_meta.identifier,
            args=ast.arguments(
                args=[
                    ast.arg(
                        arg="params",
                        annotation=ast.Name(id=self.action_meta.parameters.__name__),
                    ),
                    ast.arg(arg="soar", annotation=ast.Name(id="SOARClient")),
                    ast.arg(arg="asset", annotation=ast.Name(id="Asset")),
                ],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=[
                ast.Raise(
                    ast.Call(
                        func=ast.Name(id="NotImplementedError"), args=[], keywords=[]
                    )
                )
            ],
            decorator_list=[
                ast.Call(
                    func=ast.Name(id="app.action", ctx=ast.Load()),
                    args=[],
                    keywords=decorator_keywords,
                )
            ],
            returns=return_type,
            type_params=[],
        )
        yield ast.fix_missing_locations(node)

    def render_parameters(self) -> Iterator[str]:
        """
        Generates the code for the action parameters.
        Returns:
            str: The rendered code for the action parameters.
        """
        template = self.jinja_env.get_template("action_param.py.jinja")
        for field_name_str, field_def in self.action_meta.parameters.__fields__.items():
            field_name = normalize_field_name(field_name_str)
            yield template.render(
                name=field_name.normalized,
                alias=field_name.original if field_name.modified else None,
                py_type=field_def.annotation,
                description=field_def.field_info.description,
                required=field_def.required,
                primary=field_def.field_info.extra.get("primary", False),
                default=field_def.field_info.default,
                is_str=isinstance(field_def.field_info.default, str),
                value_list=field_def.field_info.extra.get("value_list"),
                contains=field_def.field_info.extra.get("contains"),
                allow_list=field_def.field_info.extra.get("allow_list", False),
                data_type=field_def.field_info.extra.get("data_type", "text"),
            )

    def render_outputs(
        self, model: Optional[type[ActionOutput]] = None
    ) -> Iterator[str]:
        """
        Recursively renders the Python code which would define
        the given Pydantic model (and all its nested models)
        Args:
            model (Type[ActionOutput]): The Pydantic model class to print.
        """
        if model is None:
            model = self.action_meta.output

        if model is ActionOutput:
            return

        # Using a dict because we want deduplication and order preservation. Values are not used.
        model_tree: dict[str, None] = {}
        model_lines = []

        for field_name_str, field in model.__fields__.items():
            annotation = field.annotation
            annotation_str = "{name}"
            while typing.get_origin(annotation) is list:
                annotation_str = f"list[{annotation_str}]"
                annotation = typing.get_args(annotation)[0]
            annotation_str = annotation_str.format(name=annotation.__name__)

            field_name = normalize_field_name(field_name_str)
            if field.alias != field_name.normalized:
                field_name.original = field.alias
                field_name.modified = True

            field_str = f"{field_name.normalized}: {annotation_str}"

            if issubclass(annotation, ActionOutput):
                # If the field is a Pydantic model, recursively print its fields
                for model_str in self.render_outputs(field.type_):
                    model_tree[model_str] = None

                if field_name.modified:
                    field_str += f" = OutputField(alias='{field_name.original}')"
            else:
                if (extras := {**field.field_info.extra}) or field_name.modified:
                    extras["example_values"] = extras.pop("examples", None)
                    if extras["example_values"] == [True, False]:
                        extras["example_values"] = None

                    extras_str = ", ".join(
                        f"{k}={v}" for k, v in extras.items() if v is not None
                    )

                    alias_str = (
                        f"alias='{field_name.original}'" if field_name.modified else ""
                    )

                    if extras_str or alias_str:
                        args_str = ", ".join(filter(None, (alias_str, extras_str)))
                        field_str += f" = OutputField({args_str})"

            model_lines.append(field_str)

        model_str = f"class {model.__name__}(ActionOutput):\n"
        for line in model_lines:
            model_str += f"    {line}\n"

        model_tree[model_str] = None
        yield from model_tree

    def render_outputs_ast(
        self, model: Optional[type[ActionOutput]] = None
    ) -> Iterator[ast.ClassDef]:
        """
        Generates the AST for the action outputs.

        Args:
            model (Type[ActionOutput]): The Pydantic model class to print.

        Returns:
            Iterator[ast.ClassDef]: An iterator of AST ClassDef nodes representing the action outputs.
        """
        if model is None:
            model = self.action_meta.output

        if model is ActionOutput:
            return

        model_tree: dict[str, ast.ClassDef] = {}

        field_defs: list[ast.stmt] = []

        for field_name_str, field in model.__fields__.items():
            annotation = field.annotation
            annotation_str = "{name}"
            while typing.get_origin(annotation) is list:
                annotation_str = f"list[{annotation_str}]"
                annotation = typing.get_args(annotation)[0]
            annotation_str = annotation_str.format(name=annotation.__name__)

            field_name = normalize_field_name(field_name_str)
            if field.alias != field_name.normalized:
                field_name.original = field.alias
                field_name.modified = True

            field_def_ast = ast.AnnAssign(
                target=ast.Name(id=field_name.normalized, ctx=ast.Store()),
                annotation=ast.Name(id=annotation_str, ctx=ast.Load()),
                simple=1,
            )

            if issubclass(annotation, ActionOutput):
                # If the field is a Pydantic model, recursively print its fields
                for model_ast in self.render_outputs_ast(field.type_):
                    model_tree[model_ast.name] = model_ast

                if field_name.modified:
                    field_def_ast.value = ast.Call(
                        func=ast.Name(id="OutputField", ctx=ast.Load()),
                        args=[],
                        keywords=[
                            ast.keyword(
                                arg="alias",
                                value=ast.Constant(value=field_name.original),
                            )
                        ],
                    )
            else:
                keywords = []
                if (extras := {**field.field_info.extra}) or field_name.modified:
                    extras["example_values"] = extras.pop("examples", None)
                    if extras["example_values"] == [True, False]:
                        extras["example_values"] = None

                    for k, v in extras.items():
                        if v is not None:
                            keywords.append(
                                ast.keyword(arg=k, value=ast.Constant(value=v))
                            )

                    if field_name.modified:
                        keywords.append(
                            ast.keyword(
                                arg="alias",
                                value=ast.Constant(value=field_name.original),
                            )
                        )

                if keywords:
                    field_def_ast.value = ast.Call(
                        func=ast.Name(id="OutputField", ctx=ast.Load()),
                        args=[],
                        keywords=keywords,
                    )

            field_defs.append(field_def_ast)

        if not field_defs:
            # If no fields were defined, we add a pass statement to the class body.
            field_defs.append(ast.Pass())

        model_tree[model.__name__] = ast.ClassDef(
            name=model.__name__,
            bases=[ast.Name(id="ActionOutput", ctx=ast.Load())],
            body=field_defs,
            decorator_list=[],
            keywords=[],
        )

        yield from model_tree.values()

    def render_params_ast(self) -> ast.ClassDef:
        """
        Generates the AST for the action parameters.
        Returns:
            ast.ClassDef: The AST representation of the action parameters.
        """
        params_class_name = self.action_meta.parameters.__name__
        params_class = ast.ClassDef(
            name=params_class_name,
            bases=[ast.Name(id="Params", ctx=ast.Load())],
            body=[],
            decorator_list=[],
            keywords=[],
        )

        for field_name, field_def in self.action_meta.parameters.__fields__.items():
            field_type = ast.Name(id=field_def.annotation.__name__, ctx=ast.Load())

            param = ast.Call(
                func=ast.Name(id="Param", ctx=ast.Load()),
                args=[],
                keywords=[],
            )

            if field_def.field_info.description:
                param.keywords.append(
                    ast.keyword(
                        arg="description",
                        value=ast.Constant(value=field_def.field_info.description),
                    )
                )
            if not field_def.field_info.extra.get("required", True):
                param.keywords.append(
                    ast.keyword(arg="required", value=ast.Constant(value=False))
                )
            if field_def.field_info.extra.get("primary", False):
                param.keywords.append(
                    ast.keyword(arg="primary", value=ast.Constant(value=True))
                )
            if (default := field_def.field_info.default) and default != Undefined:
                param.keywords.append(
                    ast.keyword(
                        arg="default",
                        value=ast.Constant(value=field_def.field_info.default),
                    )
                )
            if value_list := field_def.field_info.extra.get("value_list"):
                param.keywords.append(
                    ast.keyword(
                        arg="value_list",
                        value=ast.List(
                            elts=[ast.Constant(value=v) for v in value_list],
                            ctx=ast.Load(),
                        ),
                    )
                )
            if cef_types := field_def.field_info.extra.get("cef_types"):
                param.keywords.append(
                    ast.keyword(
                        arg="cef_types",
                        value=ast.List(
                            elts=[ast.Constant(value=v) for v in cef_types],
                            ctx=ast.Load(),
                        ),
                    )
                )
            if field_def.field_info.extra.get("allow_list", False):
                param.keywords.append(
                    ast.keyword(arg="allow_list", value=ast.Constant(value=True))
                )

            field_def_ast = ast.AnnAssign(
                target=ast.Name(id=field_name, ctx=ast.Store()),
                annotation=field_type,
                value=param if param.keywords else None,
                simple=1,
            )

            params_class.body.append(field_def_ast)

        if not params_class.body:
            params_class.body.append(ast.Pass())

        return params_class
