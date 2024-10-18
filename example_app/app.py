#!/usr/bin/python

from soar_sdk.app import App
from soar_sdk.params import Params

app = App()


@app.action(action_type="test")
def test_connectivity(ctx: App, param: Params):
    ctx.debug("params", param.json())
    return True, "Connectivity is here"


if __name__ == "__main__":
    app.run()
