from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput
from httpx import Response, RequestError
import pytest
from soar_sdk.exceptions import SoarAPIError, ActionFailure


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
        Response(
            201,
            json={
                "message": "Mocked container created",
                "existing_container_id": 1,
                "artifacts": [{"random_failure": "error"}],
            },
        ),
    ],
)
def test_create_container_with_artifact(
    app_connector, mock_post_container, mock_response
):
    mock_post_container.return_value = mock_response

    artifact = {
        "name": "test artifact",
        "run_automation": False,
        "source_data_identifier": None,
    }
    app_connector.container.set_executing_asset("1")
    container = {
        "name": "test container",
        "description": "test description",
        "label": "events",
        "artifacts": [artifact],
    }
    assert app_connector.container.create(container) == 1
    assert mock_post_container.called


def test_malformed_container(app_connector):
    container = {
        "name": "test container",
        "description": "test description",
        "label": "events",
    }
    with pytest.raises(ActionFailure):
        app_connector.container.create(container)

    container = {"name": "test", "data": {1, 2, 3}, "asset_id": "1"}
    with pytest.raises(ActionFailure):
        app_connector.container.create(container)


def test_create_container_failed(app_connector, mock_post_container):
    mock_post_container.return_value = Response(
        status_code=200, json={"failed": "something went wrong"}
    )

    container = {
        "name": "test container",
        "description": "test description",
        "label": "events",
        "asset_id": "1",
    }

    with pytest.raises(SoarAPIError):
        app_connector.container.create(container)

    mock_post_container.return_value = Response(
        status_code=201, json={"existing_container_id": "2"}
    )

    with pytest.raises(SoarAPIError):
        app_connector.container.create(container, fail_on_duplicate=True)


def test_create_container_locally(app_with_action: App, app_connector):
    app_connector.client.headers.pop("X-CSRFToken")

    @app_with_action.action()
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


def test_container_rest_call_failed(app_connector, mock_post_container):
    mock_post_container.side_effect = RequestError("Failed to create container")

    container = {
        "name": "test container",
        "description": "test description",
        "label": "events",
        "asset_id": "1",
    }
    with pytest.raises(SoarAPIError):
        app_connector.container.create(container)
