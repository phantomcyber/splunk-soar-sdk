from unittest import mock

from src.app import app, test_connectivity
from soar_sdk.params import Params


def test_app_test_connectivity_action() -> None:
    with mock.patch.object(
        app.manager.soar_client, "save_progress"
    ) as mock_save_progress:
        test_connectivity(Params())  # calling the action!

    mock_save_progress.assert_called_with("Connectivity checked!")
