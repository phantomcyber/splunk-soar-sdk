# `test_app.py` default file contents

This file is provided in the app by default to give you a starting point for writing your own
app tests for the actions functionality.

For testing apps the SDK rely on pytest. It also provides extra mocks and fixtures that will be useful in your
app development. For more on the app testing check the [dedicated documentation section](/docs/testing/index.md).

The basic app test file contents are as follow:

```python
from unittest import mock

from src.app import app, test_connectivity
from soar_sdk.params import Params


def test_app_test_connectivity_action():
    with mock.patch.object(
        app.manager.soar_client, "save_progress"
    ) as mock_save_progress:
        test_connectivity(Params())  # calling the action!

    mock_save_progress.assert_called_with("Connectivity checked!")

```

# Decomposing the file

The first test is simply running the `test_connectivity` action.
Note the difference between the function defined for decoration with `app.action` and the actual decorated function
we call in the test. We call the decorated function "action", and its declaration looks a little bit different. This
is the actual action declaration (from the SDK source code):

```python
            def inner(
                params: Params,
                /,
                client: SOARClient = self.actions_provider.soar_client,
                *args: Iterable[Any],
                **kwargs: dict[str, Any],
            ) -> bool:
```

As you can see, only the params are expected. By default, the `client` argument is set by SDK itself, to provide
a proper implementation of the SOAR API. You can overwrite this in your tests to mock calls to the SOAR platform
and run your tests independently offline.

Also note that the action is not returning the `ActionResult` instance or tuple, but simply the action result status
value (`boolean`).

The `Params` class if the default params model containing no params defined. It should be used as the base class
for creating your own models. For more about this check the [action params documentation page](/docs/actions/action_params.md).

# Next steps

Now that you have seen the contents of the app. Let's see [the default pre-commit configuration for the app](./pre-commit-config.yml.md)
