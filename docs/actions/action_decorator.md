# Action Decorator

The Apps SDK aims to simplify actions creation to the maximum so you can focus on actual development of the action code.
The Action decorator is the core functionality of the SDK. It moves the boilerplate, repeatable work to the SDK engine
leaving space for writing the actual action implementation.

The main responsibility of the decorator is to convert the python function into the Action, which is a meta-described
function with extra information (e.g. its name, description, or params).

Moreover, when decorating the function (on the module importing process), it is instantly verified against the necessary
setup. So if you miss the action params, or description, you will know even before the code is executed in the runtime.
As soon, as you import the action to your tests, you will know if it is properly defined.

The main responsibilities of the decorator are:
- validation of [the Params model](./action_params.md)
- replacement of the decorated function with its own function for running actions
- registration of the action for the app
- extension of the action with its meta information (e.g. name, description, type)
- handling of the returned Action Result (**FIXME** this is subject to change and actions will return Output instance instead)

For more on well constructed actions, check the [Action Anatomy docs](./action_anatomy.md).

The simplest use of decator from your app will look like this:

```python
@app.action()
```

## The Decorator Params

Most of the "magic" happens based on your function name, its params, return types, and the docstring (used for generating
the action description and documentation). But you can still add more details to your action or override the implicitly
derived information, by using the decorator keywords arguments.

### `name: str`

Name of the action that will be used in the SOAR platform UI and the app documentation. By default, the name is generated
automatically from the function name, by replacing `_` with spaces.

### `identifier: str`

The unique identifier of the action in the app context. This should always be lowercase, snake case valid string. By
default, the name of the python function is being used for this.

### `description :str`

A description of the action that is being used for the app documentation in the SOAR platform. By default, the SDK uses
the docstring of the action function. It is important to provide a helpful description of the action, so it is easier
to understand its usage for the end-user in the Visual Playbook Editor of the SOAR platform. Doing so with docstring
you will also properly document your code.

### `verbose: str`

An extended description of what the action does. It can provide extra technical details on the way the action works.
This field is not required strictly by SOAR platform and by default it is just an empty string.

### `type: str`

A type of action. The possible values are: `"contain"`, `"correct"`, `"generic"`,
`"ingest"` (for `on poll` actions), `"investigate"`, or `"test"`.
Keep in mind, that the `test_connection` action must always be set to the `"test"` type. This is why it has it set in
the [basic_app template](/app_templates/basic_app/src/app.py).

The default value set by the decorator is `"generic"`.

**Note:** this param is a subject to change and in the future will be replaced by an explicit enum, so you will use enum
values for defining the type.

### `read_only: bool`

Informs, whether the action is performing changes in the asset's system. When only gathering information from the external
systems, this will be usually `True`. If your action is performing some modifying actions on the integrated system (asset)
you should set this to `False`. Some users in the SOAR platform may be limited to the read-only actions.

The default value is `True`.

### `params_class: Type[Params]`

Each action has params passed to the `params` argument of the action function. The type of the argument needs to be set,
and it should inherit from `soar_sdk.params.Params` class. By default, the decorator uses a type provided in the function
declaration for the `params` argument:

```python
def my_action(params: MyActionParams, client: SOARClient)
```

If, for any reason, you cannot provide this class as a type hint, you can provide it explicitly as the `params_class`
keyword argument for action. It will be used in place of the default functionality.

### `output_class: Type[ActionOutput]`

Each action has a return type, which is usually a structured JSON object. The type of this object should inherit from the `soar_sdk.action_results.ActionOutput` class. This type can be specified in the decorator, but it defaults to using the return type of the handler function.

```python
def my_action(params: MyActionParams, client: SOARClient) -> MyActionOutput
```

For more info, see the [Action Outputs page](./action_outputs.md).

### `versions`

With this parameter you can define, which versions of the SOAR platform this action will work with. For more, consult
[the official documentation page](https://docs.splunk.com/Documentation/SOAR/current/DevelopApps/Metadata#Action_Section:_Versions).

The default value is `"EQ(*)"`.
