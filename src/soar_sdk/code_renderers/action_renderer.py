import textwrap
from typing import ClassVar, Optional
from collections.abc import Iterator
import typing
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

    def render_parameters(self) -> Iterator[str]:
        """
        Generates the code for the action parameters.
        Returns:
            str: The rendered code for the action parameters.
        """
        template = self.jinja_env.get_template("action_params.py.jinja")
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
