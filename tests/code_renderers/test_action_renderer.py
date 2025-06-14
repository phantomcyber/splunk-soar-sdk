import textwrap

import pytest
from soar_sdk.code_renderers.action_renderer import ActionRenderer
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.params import Params


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


@pytest.fixture
def action_meta() -> ActionMeta:
    return ActionMeta(
        action="example action",
        identifier="example_action",
        description="An example action for testing.",
        type="example",
        read_only=False,
        parameters=Params,
        output=ExampleActionOutput,
    )


def test_render_outputs(action_meta) -> None:
    expected_output = [
        textwrap.dedent(model).rstrip()
        for model in (
            """
            class ExampleInnerData(ActionOutput):
                inner_string: str = OutputField(example_values=['example_value_1', 'example_value_2'])
                weird_name: str = OutputField(alias='weird@name')
                is_example: bool
            """,
            """
            class ExampleActionOutput(ActionOutput):
                stringy_field: str
                list_of_strings: list[str]
                nested_lists: list[list[int]]
                cef_data: str = OutputField(cef_types=['ip'], example_values=['192.168.0.1', '1.1.1.1'])
                nested_type: ExampleInnerData = OutputField(alias='nested!type')
                list_of_types: list[ExampleInnerData]
                odd_field: str = OutputField(alias='odd-field', example_values=['default_value'])
            """,
        )
    ]

    renderer = ActionRenderer(action_meta)
    output_models = list(renderer.render_outputs())

    assert len(output_models) == len(expected_output)
    for actual, expected in zip(output_models, expected_output):
        assert actual.strip() == expected.strip(), (
            f"Expected:\n{expected}\nGot:\n{actual}"
        )


def test_render_empty_outputs(action_meta) -> None:
    action_meta.output = ActionOutput
    renderer = ActionRenderer(action_meta)
    output_models = list(renderer.render_outputs())

    assert output_models == [], (
        "Expected no output models for an action with no outputs."
    )
