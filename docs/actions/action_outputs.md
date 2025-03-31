# Action Outputs

The output format of your action can be defined as a simple Python class, extending the `ActionOutput` class.

```python
class ReverseStringOutput(ActionOutput):
    reversed_string: str
```

This output schema can be attached to your action via an argument to the decorator, or by using a return type hint.

```python
class ReverseStringParams(Params):
    input_string = Param(0, "Input String", data_type="string")


class ReverseStringOutput(ActionOutput):
    reversed_string: str


@app.action(params_class=ReverseStringParams, output_class=ReverseStringOutput)
def reverse_string_via_decorator(params, client):
    return ReverseStringOutput(reversed_string=params.input_string[::-1])


@app.action()
def reverse_string_via_type_hint(params: ReverseStringParams, client: SOARClient) -> ReverseStringOutput:
    return ReverseStringOutput(reversed_string=params.input_string[::-1])
```

## CEF Types and Example Values

Extra metadata can be added to the output fields, using the `OutputField` function.

```python
class GetUserOutput(ActionOutput):
    username: str = OutputField(cef_types=["username"])
    first_name: str
    last_name: str
    groups: list[str] = OutputField(example_values=["wheel", "docker"])
```

## Nesting and reusing output types

Output types can be nested, including as lists and lists of lists.

```python
class UserLocation(ActionOutput):
    country: str
    city: str


class EmailAddress(ActionOutput):
    email: str = OutputField(cef_types=["email"])
    is_primary: bool


class User(ActionOutput):
    username: str = OutputField(cef_types=["username"])
    first_name: str
    last_name: str
    active: bool
    email_addresses: list[EmailAddress]
    location: UserLocation
```

If multiple actions share a similar output format, they can reuse the same output class without re-declaring it.

```python
class ListUsersOutput(ActionOutput):
    count: int
    users: list[User]


class CreateUserOutput(ActionOutput):
    success: bool
    new_user: User
```

## Creating output models from dicts

You can easily "inflate" an output model from a Python dictionary. This is very useful when calling remote APIs that return JSON.

```python
@app.action()
def list_users(params: ListUsersParams, client: SOARClient) -> ListUsersOutput:
    """The following returns a dictionary:
        {
            "count": 1,
            "users": [
                {
                    "username": "jsmith",
                    "first_name": "John",
                    "last_name": "Smith",
                    "active": True,
                    "email_addresses": [
                        "jsmith@example.com",
                    ],
                    "location": "San Jose",
                }
            ]
        }
    """
    result = remote_api.list_users()
    return ListUsersOutput(**result)
```
