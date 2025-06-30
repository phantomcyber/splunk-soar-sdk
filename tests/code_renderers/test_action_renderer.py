import ast
import textwrap

import pytest
from soar_sdk.code_renderers.action_renderer import ActionRenderer
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params, Param


class ExampleEmptyOutput(ActionOutput):
    pass


class ExampleInnerData(ActionOutput):
    inner_string: str = OutputField(
        example_values=["example_value_1", "example_value_2"]
    )
    weird_name: str = OutputField(alias="weird@name")
    is_example: bool = OutputField(example_values=[True, False])


class ExampleActionOutput(ActionOutput):
    stringy_field: str
    list_of_strings: list[str]
    nested_lists: list[list[int]]
    cef_data: str = OutputField(
        cef_types=["ip"], example_values=["192.168.0.1", "1.1.1.1"]
    )
    nested_type: ExampleInnerData = OutputField(alias="nested!type")
    list_of_types: list[ExampleInnerData]
    odd_field: str = OutputField(alias="odd-field", example_values=["default_value"])
    empty_field: ExampleEmptyOutput


class ExampleParams(Params):
    string_param: str = Param(
        description="A string parameter for testing.", primary=True
    )
    int_param: int = Param(
        description="An integer parameter for testing.", required=False, default=42
    )
    bool_param: bool
    color_param: str = Param(
        description="A color parameter with a value list.",
        value_list=["red", "green", "blue"],
        cef_types=["color"],
        allow_list=True,
    )


@pytest.fixture
def action_meta() -> ActionMeta:
    return ActionMeta(
        action="example action",
        identifier="example_action",
        description="An example action for testing.",
        type="example",
        read_only=False,
        parameters=ExampleParams,
        output=ExampleActionOutput,
    )


def test_render_outputs(action_meta) -> None:
    expected_output = {
        "ExampleInnerData": "\n".join(
            [
                "class ExampleInnerData(ActionOutput):",
                "    inner_string: str = OutputField(example_values=['example_value_1', 'example_value_2'])",
                "    weird_name: str = OutputField(alias='weird@name')",
                "    is_example: bool",
            ]
        ),
        "ExampleActionOutput": "\n".join(
            [
                "class ExampleActionOutput(ActionOutput):",
                "    stringy_field: str",
                "    list_of_strings: list[str]",
                "    nested_lists: list[list[int]]",
                "    cef_data: str = OutputField(cef_types=['ip'], example_values=['192.168.0.1', '1.1.1.1'])",
                "    nested_type: ExampleInnerData = OutputField(alias='nested!type')",
                "    list_of_types: list[ExampleInnerData]",
                "    odd_field: str = OutputField(example_values=['default_value'], alias='odd-field')",
                "    empty_field: ExampleEmptyOutput",
            ]
        ),
        "ExampleEmptyOutput": "\n".join(
            [
                "class ExampleEmptyOutput(ActionOutput):",
                "    pass",
            ]
        ),
    }

    renderer = ActionRenderer(action_meta)
    output_models = {
        model.name: ast.unparse(model) for model in renderer.render_outputs_ast()
    }

    assert output_models.keys() == expected_output.keys()
    for model_name, expected_code in expected_output.items():
        assert (
            textwrap.dedent(output_models[model_name]).strip()
            == textwrap.dedent(expected_code).strip()
        ), f"Output model {model_name} does not match expected code."


def test_render_empty_outputs(action_meta) -> None:
    action_meta.output = ActionOutput
    renderer = ActionRenderer(action_meta)
    output_models = list(renderer.render_outputs_ast())

    assert output_models == [], (
        "Expected no output models for an action with no outputs."
    )


def test_render_params(action_meta) -> None:
    expected_params = "\n".join(
        [
            "class ExampleParams(Params):",
            "    string_param: str = Param(description='A string parameter for testing.', primary=True)",
            "    int_param: int = Param(description='An integer parameter for testing.', required=False, default=42)",
            "    bool_param: bool",
            "    color_param: str = Param(description='A color parameter with a value list.', value_list=['red', 'green', 'blue'], cef_types=['color'], allow_list=True)",
        ]
    )

    renderer = ActionRenderer(action_meta)
    params = ast.unparse(renderer.render_params_ast())

    assert expected_params == params


def test_render_empty_params(action_meta) -> None:
    action_meta.parameters = Params
    expected_params = "\n".join(
        [
            "class Params(Params):",
            "    pass",
        ]
    )

    renderer = ActionRenderer(action_meta)
    params = ast.unparse(renderer.render_params_ast())

    assert params == expected_params


def test_render_action(action_meta) -> None:
    expected_action = "\n".join(
        [
            "@app.action(description='An example action for testing.', action_type='example', read_only=False)",
            "def example_action(params: ExampleParams, soar: SOARClient, asset: Asset) -> ExampleActionOutput:",
            "    raise NotImplementedError()",
        ]
    )

    renderer = ActionRenderer(action_meta)

    blocks = {
        getattr(block, "name", "<UNKNOWN FIELD>"): ast.unparse(block)
        for block in renderer.render_ast()
    }

    assert set(blocks.keys()) == {
        "example_action",
        "ExampleParams",
        "ExampleActionOutput",
        "ExampleInnerData",
        "ExampleEmptyOutput",
    }

    assert blocks["example_action"] == expected_action


def test_render_action_verbose(action_meta) -> None:
    action_meta.verbose = "This is an example action for testing purposes."
    expected_action = "\n".join(
        [
            "@app.action(description='An example action for testing.', action_type='example', read_only=False, verbose='This is an example action for testing purposes.')",
            "def example_action(params: ExampleParams, soar: SOARClient, asset: Asset) -> ExampleActionOutput:",
            "    raise NotImplementedError()",
        ]
    )

    renderer = ActionRenderer(action_meta)

    blocks = {
        getattr(block, "name", "<UNKNOWN FIELD>"): ast.unparse(block)
        for block in renderer.render_ast()
    }

    assert set(blocks.keys()) == {
        "example_action",
        "ExampleParams",
        "ExampleActionOutput",
        "ExampleInnerData",
        "ExampleEmptyOutput",
    }

    assert blocks["example_action"] == expected_action


def test_render_action_read_only(action_meta) -> None:
    action_meta.read_only = True
    expected_action = "\n".join(
        [
            "@app.action(description='An example action for testing.', action_type='example')",
            "def example_action(params: ExampleParams, soar: SOARClient, asset: Asset) -> ExampleActionOutput:",
            "    raise NotImplementedError()",
        ]
    )

    renderer = ActionRenderer(action_meta)

    blocks = {
        getattr(block, "name", "<UNKNOWN FIELD>"): ast.unparse(block)
        for block in renderer.render_ast()
    }

    assert set(blocks.keys()) == {
        "example_action",
        "ExampleParams",
        "ExampleActionOutput",
        "ExampleInnerData",
        "ExampleEmptyOutput",
    }

    assert blocks["example_action"] == expected_action


def test_render_test_connectivity(action_meta) -> None:
    action_meta.action = "test connectivity"

    expected_stub = "\n".join(
        [
            "@app.test_connectivity()",
            "def test_connectivity(soar: SOARClient, asset: Asset) -> None:",
            "    raise NotImplementedError()",
        ]
    )

    renderer = ActionRenderer(action_meta)

    blocks = {
        getattr(block, "name", "<UNKNOWN FIELD>"): ast.unparse(block)
        for block in renderer.render_ast()
    }

    assert blocks["test_connectivity"] == expected_stub


def test_render_on_poll(action_meta) -> None:
    action_meta.action = "on poll"

    expected_stub = "\n".join(
        [
            "@app.on_poll()",
            "def on_poll(soar: SOARClient, asset: Asset, params: OnPollParams) -> Iterator[Union[Container, Artifact]]:",
            "    raise NotImplementedError()",
        ]
    )

    renderer = ActionRenderer(action_meta)

    blocks = {
        getattr(block, "name", "<UNKNOWN FIELD>"): ast.unparse(block)
        for block in renderer.render_ast()
    }

    assert blocks["on_poll"] == expected_stub
