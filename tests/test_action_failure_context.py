import asyncio
from collections.abc import AsyncGenerator, Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from soar_sdk._action_context import action_context, get_action_context
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import (
    ActionOutput,
    ActionResult,
    OutputField,
    PermissiveActionOutput,
)
from soar_sdk.app_client import AppClient
from soar_sdk.exceptions import ActionFailure, AssetMisconfiguration, SoarAPIError
from soar_sdk.params import MakeRequestParams, Param, Params


class TicketParams(Params):
    title: str
    token: str = Param(sensitive=True)


class Progress(ActionOutput):
    created: bool = OutputField(alias="ticket_created")


class Ticket(ActionOutput):
    identifier: str = OutputField(alias="ticket_id")
    nested: Progress


@pytest.mark.parametrize("flatten_results", [True, False])
@pytest.mark.parametrize("execution", ["sync", "async", "iterator", "async_generator"])
def test_partial_failure_execution_forms(
    simple_app, mocker, flatten_results, execution
):
    completed = []
    ticket = Ticket(identifier="INC-123", nested=Progress(created=True))

    def fail(soar):
        completed.append("ticket created")
        soar.set_summary(Progress(created=True))
        soar.set_message("Do not replace the exception message")
        raise ActionFailure("Attachment upload failed", data=[ticket])

    def sync(params: TicketParams, soar: SOARClient) -> Ticket:
        fail(soar)

    async def asynchronous(params: TicketParams, soar: SOARClient) -> Ticket:
        await asyncio.sleep(0)
        fail(soar)

    def iterator(params: TicketParams, soar: SOARClient) -> Iterator[Ticket]:
        yield Ticket(
            identifier="not explicitly attached", nested=Progress(created=False)
        )
        fail(soar)

    async def async_generator(
        params: TicketParams, soar: SOARClient
    ) -> AsyncGenerator[Ticket]:
        yield Ticket(
            identifier="not explicitly attached", nested=Progress(created=False)
        )
        fail(soar)

    function = {
        "sync": sync,
        "async": asynchronous,
        "iterator": iterator,
        "async_generator": async_generator,
    }[execution]
    action = simple_app.action(name="create ticket", flatten_results=flatten_results)(
        function
    )
    add_result = mocker.patch.object(simple_app.actions_manager, "add_result")
    add_exception = mocker.patch.object(simple_app.actions_manager, "add_exception")
    params = TicketParams(title="Investigate", token="secret")

    assert action(params) is False
    result = add_result.call_args.args[0]
    assert completed == ["ticket created"]
    assert add_result.call_count == 1
    assert result.get_status() is False
    assert result.get_message() == (
        "Action failure in create ticket: Attachment upload failed"
    )
    assert result.get_param() == params.model_dump()
    assert result.get_data() == [
        {"ticket_id": "INC-123", "nested": {"ticket_created": True}}
    ]
    assert result.get_summary() == {"ticket_created": True}
    add_exception.assert_not_called()
    assert simple_app.soar_client.get_summary() is None
    assert simple_app.soar_client.get_message() == ""


@pytest.mark.parametrize(
    "summary,expected",
    [
        (None, {"ticket_created": True}),
        ({}, {}),
        ({"attachment_uploaded": False}, {"attachment_uploaded": False}),
        (Progress(created=False), {"ticket_created": False}),
    ],
)
def test_summary_precedence_and_vendor_body(simple_app, mocker, summary, expected):
    @simple_app.action()
    def create_ticket(params: Params, soar: SOARClient) -> ActionOutput:
        soar.set_summary(Progress(created=True))
        raise ActionFailure(
            "Vendor rejected request",
            data=[{"error": {"code": 400, "details": ["invalid attachment"]}}],
            summary=summary,
        )

    add_result = mocker.patch.object(simple_app.actions_manager, "add_result")
    assert create_ticket(Params()) is False
    result = add_result.call_args.args[0]
    assert result.get_summary() == expected
    assert result.get_data() == [
        {"error": {"code": 400, "details": ["invalid attachment"]}}
    ]


@pytest.mark.parametrize(
    "failure_type", [ActionFailure, AssetMisconfiguration, SoarAPIError]
)
@pytest.mark.parametrize("data", [None, []])
def test_plain_failure_and_subclasses(simple_app, mocker, failure_type, data):
    failure = failure_type("failed", "original name", data=data)
    assert str(failure).endswith("in original name: failed")
    assert failure.args == ("failed",)

    @simple_app.action()
    def operation(params: TicketParams) -> ActionOutput:
        raise failure

    add_result = mocker.patch.object(simple_app.actions_manager, "add_result")
    params = TicketParams(title="first", token="secret")
    assert operation(params) is False
    result = add_result.call_args.args[0]
    assert result.get_param() == params.model_dump()
    assert result.get_data() == []
    assert result.get_summary() == {}
    assert result.get_message() == str(failure)
    assert "in operation: failed" in result.get_message()


@pytest.mark.parametrize("second_succeeds", [True, False])
def test_execution_context_does_not_leak(simple_app, mocker, second_succeeds):
    @simple_app.action()
    def operation(params: TicketParams, soar: SOARClient) -> ActionOutput:
        if params.title == "first":
            soar.set_summary(Progress(created=True))
            soar.set_message("first message")
            raise ActionFailure("first failed", data=[{"ticket_id": "first"}])
        assert soar.get_summary() is None
        assert soar.get_message() == ""
        if not second_succeeds:
            raise ActionFailure("second failed")
        return ActionOutput()

    add_result = mocker.patch.object(simple_app.actions_manager, "add_result")
    assert operation(TicketParams(title="first", token="first secret")) is False
    assert (
        operation(TicketParams(title="second", token="second secret"))
        is second_succeeds
    )
    result = add_result.call_args.args[0]
    assert result.get_param() == {"title": "second", "token": "second secret"}
    assert result.get_summary() == {}
    assert result.get_data() == ([{}] if second_succeeds else [])
    assert "first" not in result.get_message()


def test_permissive_output_and_explicit_result(simple_app, mocker):
    @simple_app.action()
    def operation(params: Params) -> ActionOutput:
        raise ActionFailure(
            "failed", data=[PermissiveActionOutput(vendor={"code": 42})]
        )

    add_result = mocker.patch.object(simple_app.actions_manager, "add_result")
    assert operation(Params()) is False
    assert add_result.call_args.args[0].get_data() == [{"vendor": {"code": 42}}]

    explicit = ActionResult(False, "explicit", {"provided": True})
    explicit.add_data({"ticket_id": "explicit"})
    explicit.set_summary({"explicit": True})

    @simple_app.action()
    def explicit_operation(params: Params) -> ActionOutput:
        return explicit

    assert explicit_operation(Params()) is False
    assert add_result.call_args.args[0] is explicit


def test_unexpected_generator_exception_is_recorded(simple_app, mocker):
    @simple_app.action()
    def operation(params: Params) -> Iterator[ActionOutput]:
        yield ActionOutput()
        raise ValueError("programming error")

    add_result = mocker.patch.object(simple_app.actions_manager, "add_result")
    add_exception = mocker.patch.object(simple_app.actions_manager, "add_exception")
    assert operation(Params()) is False
    assert isinstance(add_exception.call_args.args[0], ValueError)
    result = add_result.call_args.args[0]
    assert "ValueError: programming error" in result.get_message()
    assert result.get_data() == []


def test_make_request_failure_context(simple_app, mocker):
    @simple_app.make_request()
    async def request(params: MakeRequestParams, soar: SOARClient) -> ActionOutput:
        soar.set_summary(Progress(created=False))
        raise ActionFailure("HTTP 400", data=[{"error": "invalid request"}])

    add_result = mocker.patch.object(simple_app.actions_manager, "add_result")
    params = MakeRequestParams(endpoint="/tickets", http_method="get")
    assert request(params) is False
    result = add_result.call_args.args[0]
    assert result.get_message() == "Action failure in make request: HTTP 400"
    assert result.get_param() == params.model_dump()
    assert result.get_summary() == {"ticket_created": False}
    assert result.get_data() == [{"error": "invalid request"}]


def test_nested_context_restores_state(simple_app):
    client = simple_app.soar_client
    other = AppClient()
    client.set_summary(Progress(created=False))
    client.set_message("outside")
    assert get_action_context(client) is None
    with action_context(client):
        assert client.get_summary() is None
        assert client.get_message() == ""
        client.set_summary(Progress(created=True))
        client.set_message("outer")
        assert get_action_context(other) is None
        other.set_summary(Progress(created=False))
        other.set_message("other client")
        assert other.get_message() == "other client"
        assert other.get_summary() == Progress(created=False)

        def nested_failure():
            with action_context(client):
                assert client.get_summary() is None
                client.set_message("inner")
                raise ActionFailure("failed")

        with pytest.raises(ActionFailure):
            nested_failure()
        assert client.get_summary() == Progress(created=True)
        assert client.get_message() == "outer"
    assert client.get_summary() == Progress(created=False)
    assert client.get_message() == "outside"


def test_concurrent_contexts_are_isolated(simple_app):
    client = simple_app.soar_client
    barrier = Barrier(2)

    def execute(created):
        with action_context(client):
            client.set_summary(Progress(created=created))
            client.set_message(str(created))
            barrier.wait(timeout=10)
            assert client.get_summary() == Progress(created=created)
            assert client.get_message() == str(created)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(execute, [True, False]))
    assert client.get_summary() is None


def test_explicit_client_context(simple_app, mocker):
    other = AppClient()

    @simple_app.action()
    def operation(params: Params, soar: SOARClient) -> ActionOutput:
        soar.set_summary(Progress(created=True))
        raise ActionFailure("failed")

    add_result = mocker.patch.object(simple_app.actions_manager, "add_result")
    assert operation(Params(), other) is False
    assert add_result.call_args.args[0].get_summary() == {"ticket_created": True}
    assert other.get_summary() is None
    assert simple_app.soar_client.get_summary() is None
