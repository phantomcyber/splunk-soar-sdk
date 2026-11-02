from unittest import mock

import pytest
from pydantic import BaseModel, ValidationError

from soar_sdk.action_results import ActionOutput, ActionResult
from soar_sdk.models.view import ViewContext
from soar_sdk.params import Params
from soar_sdk.views.view_parser import ViewFunctionParser


class SampleViewOutput(ActionOutput):
    name: str
    value: int


class SampleComponentData(BaseModel):
    title: str
    count: int


class SampleViewParams(Params):
    query: str


class SampleViewSummary(ActionOutput):
    sid: str


def test_view_function_parser_auto_detect_output_class_from_list_annotation():
    def test_function(outputs: list[SampleViewOutput]):
        pass

    parser = ViewFunctionParser(test_function)
    assert parser.output_class == SampleViewOutput
    assert (
        ViewFunctionParser.auto_detect_output_class(test_function) is SampleViewOutput
    )


def test_view_function_parser_auto_detect_output_class_fails_no_annotation():
    def test_function(outputs):
        pass

    with pytest.raises(TypeError, match="Could not auto-detect ActionOutput class"):
        ViewFunctionParser(test_function)


def test_view_function_parser_parse_action_results_success():
    def test_function(outputs: list[SampleViewOutput]):
        pass

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    app_run_metadata = {"total_objects": 1, "total_objects_successful": 1}
    raw_all_app_runs = [(app_run_metadata, [mock_result])]

    parsed_outputs = parser.parse_action_results(raw_all_app_runs)

    assert len(parsed_outputs) == 1
    assert isinstance(parsed_outputs[0], SampleViewOutput)
    assert parsed_outputs[0].name == "test"
    assert parsed_outputs[0].value == 42


def test_view_function_parser_parse_action_results_invalid_data():
    def test_function(outputs: list[SampleViewOutput]):
        pass

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"invalid": "data"}]

    app_run_metadata = {"total_objects": 1, "total_objects_successful": 1}
    raw_all_app_runs = [(app_run_metadata, [mock_result])]

    with pytest.raises(ValueError, match="Data parsing failed for SampleViewOutput"):
        parser.parse_action_results(raw_all_app_runs)


def test_view_function_parser_execute_with_one_param():
    def test_function(outputs: list[SampleViewOutput]) -> str:
        return f"Found {len(outputs)} outputs"

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    action = "test_action"
    raw_all_app_runs = [({}, [mock_result])]
    raw_context = {
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }

    result = parser.execute(action, raw_all_app_runs, raw_context)

    assert result == "Found 1 outputs"


def test_view_function_parser_execute_invalid_raw_all_app_runs_type():
    def test_function(outputs: list[SampleViewOutput]) -> str:
        return "test"

    parser = ViewFunctionParser(test_function)

    action = "test_action"
    raw_all_app_runs = "invalid"
    raw_context = {
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }

    with pytest.raises(ValueError, match="not enough values to unpack"):
        parser.execute(action, raw_all_app_runs, raw_context)


def test_view_function_parser_auto_detect_output_class_from_direct_annotation():
    def test_function(output: SampleViewOutput):
        pass

    parser = ViewFunctionParser(test_function)
    assert parser.output_class == SampleViewOutput


def test_view_function_parser_auto_detect_output_class_invalid_type():
    def test_function(outputs: list[str]):
        pass

    with pytest.raises(TypeError, match="Could not auto-detect ActionOutput class"):
        ViewFunctionParser(test_function)


def test_view_function_parser_execute_with_two_params():
    def test_function(context: ViewContext, outputs: list[SampleViewOutput]) -> str:
        return f"Context app: {context.app}, Found {len(outputs)} outputs"

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    action = "test_action"
    raw_all_app_runs = [({}, [mock_result])]
    raw_context = ViewContext(
        QS={}, container=1, app=2, no_connection=False, google_maps_key=False
    )

    result = parser.execute(action, raw_all_app_runs, raw_context)

    assert result == "Context app: 2, Found 1 outputs"


def test_view_function_parser_execute_with_three_params():
    def test_function(
        context: ViewContext, action: str, outputs: list[SampleViewOutput]
    ) -> str:
        return f"Action: {action}, Found {len(outputs)} outputs"

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    action = "test_action"
    raw_all_app_runs = [({}, [mock_result])]
    raw_context = ViewContext(
        QS={}, container=1, app=2, no_connection=False, google_maps_key=False
    )

    result = parser.execute(action, raw_all_app_runs, raw_context)

    assert result == "Action: test_action, Found 1 outputs"


def test_view_function_parser_parse_action_results_non_dict_metadata():
    def test_function(outputs: list[SampleViewOutput]):
        pass

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    mock_metadata = mock.Mock()
    raw_all_app_runs = [(mock_metadata, [mock_result])]

    parsed_outputs = parser.parse_action_results(raw_all_app_runs)

    assert len(parsed_outputs) == 1


def test_view_function_parser_execute_context_parsing_fails():
    def test_function(outputs: list[SampleViewOutput]) -> str:
        return "test"

    parser = ViewFunctionParser(test_function)

    mock_result = mock.Mock()
    mock_result.get_data.return_value = [{"name": "test", "value": 42}]

    action = "test_action"
    raw_all_app_runs = [({}, [mock_result])]
    raw_context = {
        "QS": {},
        "container": 1,
        "app": 2,
        "no_connection": False,
        "google_maps_key": False,
    }

    result = parser.execute(action, raw_all_app_runs, raw_context)

    assert result == "test"


@pytest.fixture
def metadata_app_runs():
    first = ActionResult(True, "ok", {"query": "index=one"})
    first.set_summary({"sid": "one"})
    first.add_data({"name": "first", "value": 1})
    first.add_data({"name": "second", "value": 2})
    empty = ActionResult(True, "ok", {"query": "index=empty"})
    empty.set_summary({"sid": "empty"})
    last = ActionResult(True, "ok", {"query": "index=two"})
    last.set_summary({"sid": "two"})
    last.add_data({"name": "last", "value": 3})
    return [({}, [first, empty]), ({}, [last])]


def test_view_metadata_models_align_with_outputs_across_results_and_runs(
    metadata_app_runs,
):
    def handler(
        outputs: list[SampleViewOutput],
        *,
        params: list[SampleViewParams],
        summary: list[SampleViewSummary],
    ) -> dict:
        assert all(isinstance(item, SampleViewParams) for item in params)
        assert all(isinstance(item, SampleViewSummary) for item in summary)
        return {
            "rows": [
                (output.name, param.query, item_summary.sid)
                for output, param, item_summary in zip(
                    outputs, params, summary, strict=True
                )
            ],
            "data": [output.model_dump() for output in outputs],
        }

    result = ViewFunctionParser(handler).execute("search", metadata_app_runs, {})

    assert result == {
        "rows": [
            ("first", "index=one", "one"),
            ("second", "index=one", "one"),
            ("last", "index=two", "two"),
        ],
        "data": [
            {"name": "first", "value": 1},
            {"name": "second", "value": 2},
            {"name": "last", "value": 3},
        ],
    }


@pytest.mark.parametrize("name", ["params", "summary"])
@pytest.mark.parametrize("annotated", [False, True])
def test_view_metadata_arguments_are_individually_optional(
    metadata_app_runs, name, annotated
):
    def raw_params(outputs: list[SampleViewOutput], *, params) -> dict:
        return {"params": params}

    def raw_summary(outputs: list[SampleViewOutput], *, summary) -> dict:
        return {"summary": summary}

    def dict_params(outputs: list[SampleViewOutput], *, params: list[dict]) -> dict:
        return {"params": params}

    def dict_summary(outputs: list[SampleViewOutput], *, summary: list[dict]) -> dict:
        return {"summary": summary}

    handler = {
        ("params", False): raw_params,
        ("summary", False): raw_summary,
        ("params", True): dict_params,
        ("summary", True): dict_summary,
    }[name, annotated]

    result = ViewFunctionParser(handler).execute("search", metadata_app_runs, {})

    key, first, last = (
        ("query", "index=one", "index=two")
        if name == "params"
        else ("sid", "one", "two")
    )
    assert result == {name: [{key: first}, {key: first}, {key: last}]}


@pytest.mark.parametrize("legacy_arity", [1, 2, 3])
def test_view_metadata_preserves_existing_positional_arguments(
    metadata_app_runs, legacy_arity
):
    context = ViewContext(
        QS={}, container=1, app=2, no_connection=False, google_maps_key=False
    )

    def one(outputs: list[SampleViewOutput], *, summary: list[dict]) -> dict:
        return {"names": [output.name for output in outputs], "summary": summary}

    def two(
        ctx: ViewContext, outputs: list[SampleViewOutput], *, summary: list[dict]
    ) -> dict:
        assert ctx is context
        return one(outputs, summary=summary)

    def three(
        ctx: ViewContext,
        action: str,
        outputs: list[SampleViewOutput],
        *,
        summary: list[dict],
    ) -> dict:
        assert ctx is context
        assert action == "search"
        return one(outputs, summary=summary)

    handler = [one, two, three][legacy_arity - 1]
    result = ViewFunctionParser(handler).execute("search", metadata_app_runs, context)

    assert result == {
        "names": ["first", "second", "last"],
        "summary": [{"sid": "one"}, {"sid": "one"}, {"sid": "two"}],
    }


@pytest.mark.parametrize("empty_runs", [[], [({}, [ActionResult(True, "ok")])]])
def test_view_metadata_lists_are_empty_without_output_rows(empty_runs):
    def handler(
        outputs: list[SampleViewOutput],
        *,
        params: list[SampleViewParams],
        summary: list[SampleViewSummary],
    ) -> dict:
        return {"outputs": outputs, "params": params, "summary": summary}

    assert ViewFunctionParser(handler).execute("search", empty_runs, {}) == {
        "outputs": [],
        "params": [],
        "summary": [],
    }


def test_view_metadata_is_not_read_unless_requested(metadata_app_runs):
    for _, results in metadata_app_runs:
        for result in results:
            result.get_param = mock.Mock(
                side_effect=AssertionError("params not requested")
            )
            result.get_summary = mock.Mock(
                side_effect=AssertionError("summary not requested")
            )

    def handler(outputs: list[SampleViewOutput]) -> str:
        return outputs[0].name

    assert (
        ViewFunctionParser(handler).execute("search", metadata_app_runs, {}) == "first"
    )


def test_view_metadata_does_not_supply_the_output_model_annotation():
    def handler(outputs, *, summary: list[SampleViewSummary]) -> str:
        return "unused"

    with pytest.raises(TypeError, match="Could not auto-detect ActionOutput class"):
        ViewFunctionParser(handler)


@pytest.mark.parametrize("name", ["params", "summary"])
def test_existing_positional_output_names_are_not_magic(metadata_app_runs, name):
    def params_handler(params: list[SampleViewOutput]) -> str:
        return params[-1].name

    def summary_handler(summary: list[SampleViewOutput]) -> str:
        return summary[-1].name

    handler = params_handler if name == "params" else summary_handler
    assert (
        ViewFunctionParser(handler).execute("search", metadata_app_runs, {}) == "last"
    )


def test_view_metadata_validates_requested_models(metadata_app_runs):
    def handler(
        outputs: list[SampleViewOutput], *, params: list[SampleViewSummary]
    ) -> str:
        return "unused"

    with pytest.raises(ValidationError, match="sid"):
        ViewFunctionParser(handler).execute("search", metadata_app_runs, {})


def test_async_view_receives_aligned_metadata(metadata_app_runs):
    async def handler(
        outputs: list[SampleViewOutput],
        params: list[SampleViewParams],
        summary: list[SampleViewSummary],
    ) -> str:
        return f"{outputs[-1].name}: {params[-1].query}: {summary[-1].sid}"

    assert (
        ViewFunctionParser(handler).execute("search", metadata_app_runs, {})
        == "last: index=two: two"
    )


@pytest.mark.parametrize("name", ["params", "summary"])
@pytest.mark.parametrize("legacy_arity", [2, 3])
def test_existing_output_names_keep_their_role_with_context(
    metadata_app_runs, name, legacy_arity
):
    context = ViewContext(
        QS={}, container=1, app=2, no_connection=False, google_maps_key=False
    )

    def params_two(ctx, params: list[SampleViewOutput]) -> str:
        assert ctx is context
        return params[-1].name

    def summary_two(ctx, summary: list[SampleViewOutput]) -> str:
        assert ctx is context
        return summary[-1].name

    def params_three(ctx, action, params: list[SampleViewOutput]) -> str:
        assert ctx is context
        assert action == "search"
        return params[-1].name

    def summary_three(ctx, action, summary: list[SampleViewOutput]) -> str:
        assert ctx is context
        assert action == "search"
        return summary[-1].name

    handler = {
        ("params", 2): params_two,
        ("summary", 2): summary_two,
        ("params", 3): params_three,
        ("summary", 3): summary_three,
    }[name, legacy_arity]
    assert (
        ViewFunctionParser(handler).execute("search", metadata_app_runs, context)
        == "last"
    )


@pytest.mark.parametrize(
    "style", ["ordinary", "leading", "interleaved", "mixed", "positional_only"]
)
def test_view_metadata_is_injected_by_name_in_any_position(metadata_app_runs, style):
    def rows(outputs, params, summary):
        return [
            (output.name, param.query, item.sid)
            for output, param, item in zip(outputs, params, summary, strict=True)
        ]

    def ordinary(
        outputs: list[SampleViewOutput],
        params: list[SampleViewParams],
        summary: list[SampleViewSummary],
    ) -> list:
        return rows(outputs, params, summary)

    def leading(
        summary: list[SampleViewSummary],
        params: list[SampleViewParams],
        outputs: list[SampleViewOutput],
    ) -> list:
        return rows(outputs, params, summary)

    def interleaved(
        params: list[SampleViewParams],
        outputs: list[SampleViewOutput],
        summary: list[SampleViewSummary],
    ) -> list:
        return rows(outputs, params, summary)

    def mixed(
        params: list[SampleViewParams],
        outputs: list[SampleViewOutput],
        *,
        summary: list[SampleViewSummary],
    ) -> list:
        return rows(outputs, params, summary)

    def positional_only(
        summary: list[SampleViewSummary],
        /,
        outputs: list[SampleViewOutput],
        params: list[SampleViewParams],
    ) -> list:
        return rows(outputs, params, summary)

    handler = {
        "ordinary": ordinary,
        "leading": leading,
        "interleaved": interleaved,
        "mixed": mixed,
        "positional_only": positional_only,
    }[style]
    assert ViewFunctionParser(handler).execute("search", metadata_app_runs, {}) == [
        ("first", "index=one", "one"),
        ("second", "index=one", "one"),
        ("last", "index=two", "two"),
    ]


def test_view_metadata_can_be_interleaved_with_context_and_action(metadata_app_runs):
    context = ViewContext(
        QS={}, container=1, app=2, no_connection=False, google_maps_key=False
    )

    def handler(
        summary: list[SampleViewSummary],
        ctx: ViewContext,
        params: list[SampleViewParams],
        action: str,
        outputs: list[SampleViewOutput],
    ) -> str:
        assert ctx is context
        return f"{action}: {outputs[-1].name}: {params[-1].query}: {summary[-1].sid}"

    assert (
        ViewFunctionParser(handler).execute("search", metadata_app_runs, context)
        == "search: last: index=two: two"
    )


def test_view_metadata_preserves_forwarded_args_and_kwargs(metadata_app_runs):
    def handler(
        ctx,
        action,
        outputs: list[SampleViewOutput],
        params: list[dict],
        *args,
        summary: list[dict],
        **kwargs,
    ) -> dict:
        return {
            "outputs": [item.name for item in outputs],
            "params": params,
            "summary": summary,
            "args": args,
            "kwargs": kwargs,
        }

    result = ViewFunctionParser(handler).execute(
        "search", metadata_app_runs, {}, "extra", option=True
    )

    assert result == {
        "outputs": ["first", "second", "last"],
        "params": [
            {"query": "index=one"},
            {"query": "index=one"},
            {"query": "index=two"},
        ],
        "summary": [{"sid": "one"}, {"sid": "one"}, {"sid": "two"}],
        "args": ("extra",),
        "kwargs": {"option": True},
    }
