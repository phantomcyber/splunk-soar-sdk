# `src/app.py` default file contents

This document will dive deeper into the initial structure of the `app.py`
file when starting working with Apps.

The file consists of three main parts:
1. App initialization
1. Actions definitions
1. App run for running the actions app actions directly

Here's the default `app.py` file contents available in the basic app template

```python
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
```

# Decomposing the file

Let's dive deeper into each part of the file above:

```python
app = App()
```

This is how you initialize the basic default app instance. The app object will be used
by actions below. Keep in mind this object variable and its path are pointed in `pyproject.toml`
so the SOAR App Engine knows where the app instance is provided.

```python
@app.action(action_type="test")
```

We create an action by decorating a function with the `app.action` decorator. The default `action_type`
is `generic`, so usually you will not have to provide this argument for the decorator. This is not the
case for the `test` action type though, so we provide this type here explicitly.

All apps must provide the `test_connectivity` action in order be installed in the first place.
Note that the action identifier must be exactly "test_connectivity" and the action type needs
to be set to "test".

```python
def test_connectivity(params: Params, client: SOARClient):
```

The function declaration is important part of defining the action.
The function name is - by default - used as the action identifier.
The arguments for the action should always be:
- `params` - a model class inheriting from `soar_sdk.params.Params`.
The provided class typehint is used by SDK to generate action
params list in the Manifest, so it needs to be always provided
and will raise exception otherwise.
- `client` - an instance of the `SOARClient` implementation providing API for
interacting with SOAR platform app engine.

```python
    """Testing the connectivity service."""
```
The docstring for the action is used by default to create
the action description in the manifest and the documentation
of the SOAR platform web UI.

```python
    client.save_progress("Connectivity checked!")
```

This line will simply send a log on the progress of the action to the SOAR app engine.

```python
    return True, "Connectivity checked!"
```

The action must have at least one Action Result set with at least the action success
or failure status (represented by boolean values of `True` or `False`). The action in
SDK has one Action Result created automatically from the returned tuple consisting
of boolean result and the result message.

```pthon
if __name__ == "__main__":
    app.run()
```

The app actions can be invoked from the command line directly when provided with a properly
prepared JSON file passed as an argument. The lines above provide support for calling the
`app.py` file as python script and process the action with the JSON file.

You should always provide these lines to enable app to be run as a script.

# Next step

In the next step we will see [the default contents of the `test_app.py` file with tests for actions](./test_app.py.md).

# Related pages

- [App configuration](/docs/app_configuration.md)
- [Actions documentation](/docs/actions/index.md)
- [Writing tests](/docs/testing/index.md)
