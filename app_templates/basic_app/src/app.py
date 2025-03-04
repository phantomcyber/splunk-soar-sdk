#!/usr/bin/python
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Params

app = App()


@app.action(action_type="test")
def test_connectivity(params: Params, client: SOARClient) -> tuple[bool, str]:
    """Testing the connectivity service."""
    client.save_progress("Connectivity checked!")
    return True, "Connectivity checked!"


if __name__ == "__main__":
    app.run()
