# Action Anatomy

The Apps SDK introduces an entirely new way of building Splunk SOAR Apps. It was designed following the best
leading frameworks in Python ecosystem. Its goal is to let you build your own app and actions simply and with
good practices in mind.

The new design follows the modern trends in building python code. It introduces a more direct and explicit exposure
of the available functionality, hiding and implicitly running your app at the same time, removing the unnecessary
boilerplate.

At the core of the app development lies creation of Actions. Each action is a python function decorated with your
app's `action` decorator. You can learn more on [the decorator on its dedicated doc page](./action_decorator.md).

This page decomposes the Action structure giving you more details on how each element participates in defining the Action.
Let's take another look at the simple action code:

```python

@app.action( # 1. Action Decorator
    name="Custom Name Action", # 2. Decorator Params
)
def my_action(  # 3. Action Function
    params: MyActionParams,  # 4. Action Params
    client: SOARClient,  # 5. SOAR Client
):
    """The action that does what I want it to do"""  # 6. Action Description
    return True, "Action succeeded"  # 7. Action Result
```

## 1. Action Decorator

The decorator is provided in the instance of your app. It does most of the implicit magic under the hood
taking care of converting the function into the complete action.

The decorator returns its own decorated function which is extended with meta information and has mechanisms for
validating params, and handling the returned values.

## 2. Decorator Params

When decorating your function, the action decorator does many default conversions under the hood. These can be
overridden using the params passed to it. In most cases you won't need to use them as they are set by default to
the most common use cases. Sometimes though it will be necessary to set some params.

You can read more on [the decorator itself on the separate docs page](./action_decorator.md).

## 3. Action Function

It is just a regular python function. Keep in mind that the name of the function will be also a name and identifier
of the action used in the manifest file and the platform.

Every action function must have the same two arguments named using the expected names:
- `params` contains the params passed to the action in the runtime
- `client` is an instance of the SOAR Client providing API for interacting with SOAR platform when performing the action

## 4. Action Params

The `params` argument will contain the data passed to the action in the runtime. Usually, this will be the data passed
from another action in the Playbook, or directly by an investigator in the process of working with containers.

Every action needs to specify the type of this argument with a typehint. The type should be a class inheriting from
`soar_sdk.params.Params` class. It is a dedicated pydantic model, which is responsible for validating the data passed into
the action, and defining the expected data types for the manifest file.

You can read more about [building the Params Models on a separate docs page](./action_params.md).

## 5. SOAR Client

The SOAR client is the instance of the object responsible for communicating with the SOAR platform. When running
your action the instance is being injected into your action by the SDK.

The default SOAR Client is connected to the SOAR platform and as such will require it to be set up for running the code.
But, when testing your actions, you can pass your own SOAR client mock overwriting the default one. That way you
don't need a running SOAR platform for testing your actions.

For this argument you should always set `soar_sdk.abstract.SOARClient` as the type, to get the best hints support in your
IDE.

You can learn more on actions testing in [the testing docs pages](/docs/testing/index.md).

## 6. Asset State

The Splunk SOAR platform can preserve some state data in between action runs. This data is stored on the filesystem of the SOAR instance or Automation Broker running the action, and is tied to each individual asset.

State is divided into three dictionaries, which can be accessed from the `SOARClient` object:

- `client.ingestion_state`: stores checkpoints and other data used during polling operations
- `client.auth_state`: stores session tokens and other authentication data
- `client.asset_cache`: stores other arbitrary data that can be reused between action runs

These properties are automatically loaded from the filesystem before the action handler function is invoked, and any updates are saved to the filesystem after the handler exits.

State is not encrypted by default, so apps should take care to encrypt any secret data before storing it.

```python
@app.action()
def my_stateful_action(params: Params, asset: Asset, client: SOARClient) -> MyActionOutput:
    if not (session_token := client.auth_state.get("session_token")):
        session_token = my_api.get_session_token(asset.client_id, asset.client_secret)
        client.auth_state["session_token"] = session_token

    result = my_api.do_something(session_token)
    return MyActionOutput(**result)
```

## 7. Action Description

The docstring is another important part of creating your action. The SDK is using it to generate the action description
for the app manifest and the documentation in the platform. This method not only documents well your code, but also
allows to build a documentation for the actions use in the SOAR platform.

You can pass the `description` param in the `action` decorator to differentiate your code docstring from the actual
description, but in most cases you will want both to be the same.

## 8. Action Result

**NOTE:** this functionality is still subject to change - the returned type in the future will be Output, so this doc
will require updates.

Each action should return at least information of whether it has succeeded or failed. We call this an Action Result.
The result should have the status on the success (`True` or `False`) and an extra verbose description on the status
(which can be also an empty string).

You can create more than one action result for the action. At least one must be created for the action. The SDK
takes care of that automatically by creating and reporting one from the returned tuple.

[Read more on Action Results](./action_results.md)
