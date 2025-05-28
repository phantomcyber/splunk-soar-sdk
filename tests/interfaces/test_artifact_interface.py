from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput
from httpx import Response, RequestError


def test_create_artifact(app_with_action: App, app_connector, mock_post_artifact):
    @app_with_action.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        artifact = {
            "name": "test artifact",
            "container_id": 1,
            "cef": {
                "fileName": "test.txt",
            },
            "run_automation": False,
            "source_data_identifier": None,
        }
        soar.artifact.create(artifact)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert result
    assert mock_post_artifact.called


def test_create_artifact_bad_json(app_with_action: App, app_connector):
    @app_with_action.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        artifact = {"name": "test", "data": {1, 2, 3}}
        soar.artifact.create(artifact)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert not result


def test_save_artifact_failed(app_with_action: App, app_connector, mock_post_artifact):
    mock_post_artifact.return_value = Response(
        status_code=200, json={"failed": "something went wrong"}
    )

    @app_with_action.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        artifact = {
            "name": "test artifact",
            "container_id": 1,
            "run_automation": False,
            "source_data_identifier": None,
        }
        soar.artifact.create(artifact)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert not result


def test_create_artifact_exisiting_id(
    app_with_action: App, app_connector, mock_post_artifact
):
    mock_post_artifact.return_value = Response(
        status_code=201, json={"existing_artifact_id": "2"}
    )

    @app_with_action.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        artifact = {
            "name": "test artifact",
            "container_id": 1,
            "run_automation": False,
            "source_data_identifier": None,
        }
        soar.artifact.create(artifact)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert result


def test_save_artifact_locally(app_with_action: App, app_connector):
    app_connector.client.headers.pop("X-CSRFToken")

    @app_with_action.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        artifact = {
            "name": "test artifact",
            "container_id": 1,
            "run_automation": False,
            "source_data_identifier": None,
        }
        soar.artifact.create(artifact)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert result


def test_save_artifact_locally_missing_container(app_with_action: App, app_connector):
    app_connector.client.headers.pop("X-CSRFToken")

    @app_with_action.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        artifact = {
            "name": "test artifact",
            "run_automation": False,
            "source_data_identifier": None,
        }
        soar.artifact.create(artifact)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert not result


def test_artifact_rest_call_failed(
    app_with_action: App, app_connector, mock_post_artifact
):
    mock_post_artifact.side_effect = RequestError("Failed to create artifact")

    @app_with_action.action()
    def action_function(params: Params, soar: SOARClient) -> ActionOutput:
        artifact = {
            "name": "test artifact",
            "container_id": 1,
            "run_automation": False,
            "source_data_identifier": None,
        }
        soar.artifact.create(artifact)
        return ActionOutput()

    result = action_function(Params(), soar=app_connector)
    assert not result
