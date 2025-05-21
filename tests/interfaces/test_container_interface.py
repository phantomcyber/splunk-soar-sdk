from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput
from httpx import Response, RequestError
import pytest


@pytest.mark.parametrize(
    "mock_response",
    [
        Response(
            201,
            json={
                "message": "Mocked container created",
                "id": 1,
                "artifacts": [{"id": "2"}],
            },
        ),
        Response(
            201,
            json={
                "message": "Mocked container created",
                "id": 1,
                "artifacts": [{"existing_artifact_id": "2"}],
            },
        ),
        Response(
            201,
            json={
                "message": "Mocked container created",
                "id": 1,
                "artifacts": [{"failed": "error"}],
            },
        ),
        Response(
            201,
            json={
                "message": "Mocked container created",
                "id": 1,
                "artifacts": [{"random_failure": "error"}],
            },
        ),
    ],
)
def test_create_container_with_artifact(
    simple_app: App, app_connector, mock_post_container, mock_response
):
    mock_post_container.return_value = mock_response

    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        artifact = {
            "name": "test artifact",
            "run_automation": False,
            "source_data_identifier": None,
        }
        soar.container.set_executing_asset("1")
        container = {
            "name": "test container",
            "description": "test description",
            "label": "events",
            "artifacts": [artifact],
        }
        soar.container.create(container)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert result
    assert mock_post_container.called


def test_malformed_container(simple_app: App, app_connector):
    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        container = {
            "name": "test container",
            "description": "test description",
            "label": "events",
        }
        soar.container.create(container)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert not result

    @simple_app.action()
    def bad_json(params: Params, soar: SOARClient) -> ActionOutput:
        container = {"name": "test", "data": {1, 2, 3}, "asset_id": "1"}
        soar.container.create(container)
        return ActionOutput()

    result = bad_json(Params(), soar=app_connector)
    assert not result


def test_create_container_failed(simple_app: App, app_connector, mock_post_container):
    app_connector.csrf_token = "fake_csrf_token"
    mock_post_container.return_value = Response(
        status_code=200, json={"failed": "something went wrong"}
    )

    container = {
        "name": "test container",
        "description": "test description",
        "label": "events",
        "asset_id": "1",
    }

    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        soar.container.create(container)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert not result

    mock_post_container.return_value = Response(
        status_code=201, json={"existing_container_id": "2"}
    )

    @simple_app.action()
    def existing_id(params: Params, soar: SOARClient) -> ActionOutput:
        soar.container.create(container)
        return ActionOutput()

    result = existing_id(Params(), soar=app_connector)
    assert result


def test_create_container_locally(simple_app: App, app_connector):
    app_connector.client.headers.pop("X-CSRFToken")

    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        artifact = {
            "name": "test artifact",
            "source_data_identifier": None,
        }
        container = {
            "name": "test container",
            "description": "test description",
            "label": "events",
            "asset_id": "1",
            "artifacts": [artifact],
        }
        soar.container.create(container)
        artifact2 = {
            "name": "test artifact2",
            "source_data_identifier": None,
            "run_automation": False,
        }
        container["artifacts"] = [artifact2]
        soar.container.create(container)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert result


def test_container_rest_call_failed(
    simple_app: App, app_connector, mock_post_container
):
    mock_post_container.side_effect = RequestError("Failed to create container")

    @simple_app.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        container = {
            "name": "test container",
            "description": "test description",
            "label": "events",
            "asset_id": "1",
        }
        soar.container.create(container)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert not result
