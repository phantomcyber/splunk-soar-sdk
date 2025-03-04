
# Getting Started

In this section we will guide you through the basic process of creating your first draft of the SOAR App.

## Actions philosophy

Apps (aka Connectors) in Splunk SOAR are extensions that enrich the platform functionality.
Each app provides a new set of actions that can be used for the security investigation (also automated one,
when used in playbooks). Usually, a single app adds actions for one specific tool or 3rd party service
(e.g. whois lookup or geolocation).

When building your app, you will focus on implementing the actions like sending data to the external service
or updating the containers on SOAR platform.

This SDK is a set of tools to build, test and run your own app that will extend the SOAR installation by implementing
actions.

# Your first app

The following guide will get you through the process of building your first app, explaining
its crucial components and functionality.

## The app structure

The SDK works with the common python library structure written using poetry. You can quickly dive into
the app development by using one of the app templates available in the `app_templates` directory of the SDK repository.

To create your own app you should either copy the [`app_templates/basic_app`](/app_templates/basic_app) files as your own project directory or
create the starting directory/files structure yourself that will reflect this tree:

```shell

my_app/
├─ src/
│  ├─ __init__.py
│  ├─ app.py
├─ tests/
│  ├─ __init__.py
│  ├─ test_app.py
├─ .pre-commit-config.yaml
├─ logo.svg
├─ logo_dark.svg
├─ pyproject.toml
```

We describe and explain each of the files in full in the dedicated [documentation pages about the app structure](/docs/app_structure/index.md).

For now, let's shortly go over each of the components in the structure, so we can create our first action.

### The `src` directory and the `app.py` file

In this directory you will develop your app source code. We typically place here the `app.py` file
with the main module code. Keep in mind you can always add more python modules to this directory and import
them in the `app.py` file to create cleaner maintainable code.

In the `app.py` file we typically create the `App` instance and define actions and provide its implementation.
This module will be used in our `pyproject.toml` app configuration to point the `app` object as `main_module` for
use in SOAR platform when running actions.

[Read the detailed documentation on the `app.py` file contents](/docs/app_structure/app.py.md)

Note that the `test_connectivity` action is mandatory for each app. It is used when installing the app in
the SOAR platform and checked usually when a new asset is added for the app. This is why it is always provided
in the app scratch files.

### The `tests` directory and the `test_app.py` file

In this directory you will add unit test files for the app. The sample test file should be present there with at least
basic tests on the actions you create.

[Read the detailed documentation on the `test_app.py` file contents](/docs/app_structure/test_app.py.md)

### The `logo*.svg` files

These files are used by SOAR platform to present your application in the web UI. You should always provide
two versions of the logo. The regular one is used for light mode and the `_dark` file is used for the dark mode.

### `pyproject.toml` configuration file

This file defines the app development parameters, dependencies, and also configuration data for the app.

In this file you will define poetry dependencies (including this SDK) and basic information like the name
of the app, its version, description, authors, and other params.

[Read the detailed documentation on the `pyproject.toml` file contents](/docs/app_structure/pyproject.toml.md)


## Configuring the environment

Once you have your starting app file structure, you will need to set up your app development environment.

In your app directory install the pre-commit hooks:

```shell
pre-commit install
```

Then you need to set up the environment using poetry. It will set up the virtual environment and install
necessary dependencies:

```shell
poetry install
```


## Creating your first action

Your app should already have the `app` object instance created in the `app.py` file. In the future you will
initialize it with extra arguments, like the asset configuration, to specify the asset data. You can read more on
[how to initialize the app on the dedicated docs page](/docs/app_configuration.md).

For now let's focus on creating a very simple action and see the basics of its structure. You should already have
one action defined in your `app.py` file called `test_connectivity` which must be created in every app. You can check
how it is constructed. Our first action will be very similar to it.

The `app` instance provides the `action` decorator which is used to turn your python functions into SOAR App actions.

Here's the code of the simplest action you can create:

```python
@app.action()
def my_action(params: Params, client: SOARClient):
    """This is the first custom action in the app"""
    return True, "Action run successful"
```

Let's break down this example to explain what happens here.

### `App.action` decorator

```python
@app.action()
```

The decorator is connecting your function with the app instance and the SOAR engine.

It's responsible for many things related to running the app under the hood, so you can
focus on developing the action. Here are some things it takes care of:

- registers your action, so it is invoked when running the app in SOAR platform
- sets the configuration values for the action (which you can define by providing extra params in the call parenthesis)
- checks if the action params are provided, valid and of the proper type
- inspects your action arguments types and validates them

For more, [read the doc page dedicated to the `App.action` decorator](/docs/actions/action_decorator.md).

### The action declaration

```python
def my_action(params: Params, client: SOARClient):
```

`my_action` is the identifier of the action and as such it will be visible later in the SOAR platform.
`App.action` decorator automatically converts this to _"my action"_ string name that will be used when generating
the app Manifest file and the documentation.

Each action should accept and define `params` and `client` arguments with proper typehints.

The `params` argument should always be of the class type inherited from `soar_sdk.params.Params`.
You can [read more on defining the action params in the separate docs page](/docs/actions/action_params.md).

The `client` is automatically injected into your action function run and should not be passed when manually
calling the decorated function. You can pass it though, if you want to mock the `SOARClient` instance in your tests.
[Read more on testing the actions](/docs/testing/actions.md)

### The action description docstring

```python
    """This is the first custom action in the app"""
```

You should always provide the docstring for your action. It makes your code easier to understand and maintain, but
also, the docstring is (by defualt) used by the `App.action` decorator to generate the action description for the
app documentation in SOAR platform.

The description should be kept short and simple, explaining what the action does.

### The action result

```python
    return True, "Action run successful"
```

Each action must return at least one action result. While you can create multiple instances of the action result
and pass more than one values, the one that is most important is the general action result.

Prior to SDK, the connectors had to define and create their own `ActionResult` instances. This is simplified now
in SDK. Simply return a two-element tuple. The first value should be a `boolean` of `True` if action run was successful,
or `False` otherwise. The second tuple element is the result comment which can be useful for logging the action runs
and debugging.

[Read more on action results and outputs for actions](/docs/actions/action_outputs.md)

As you can see, this simple action is taking bare `Params` object, so with no defined params and simply returns
the result of successful run.

## Testing and building the app

### Test your app

In order to run tests (there's only one at the moment) you will use pyest in the shell of the poetry virtual env:

```shell
poetry run pytest
```

You can also enter the shell first to always work in the context of your virtual env. First run:

```shell
poetry shell
```

From this shell, you will be able to run `soarapps` commands from the SDK CLI. Now you can simply run:

```shell
pytest
```

### Generating the Manifest file

The manifest file is required by SOAR platform for installation and running apps. It provides basic information
on the app itself, lists actions with all params so they can be used in the Visual Playbook Editor, and holds
information of the dependencies along with the paths to their wheel files.

The manifest file should be always generated automatically by using the SDK tools. In order to do so, use the
SDK CLI command in your project directory:

```shell
soarapps manifests create my_app.json .
```

The json file is the target manifest JSON filename to be created. The trailing dot is a context in which the manifest
should be built. If you run this command in your app directory, the context is current dir (thus `.`).

The command uses `pyproject.toml` meta information on the app, all registered actions and their meta information
provided in the source files to generate a proper manifest file. You will need to commit this file into your repository
so it can be used for building the app artifacts.

### Building dependencies wheels

When writing your own app, you will need to use some 3rd party dependencies at some point. Since the app is running
on the SOAR platform, it provides (via SDK dependencies) some useful libraries compatible with SOAR, which you can
reuse for your needs. You can check the [SDK pyproject.toml](/pyproject.toml) file to check the available dependencies
of SDK that you can use. Since you already use SDK as a dependency, the others will be available in your development
environment as well (and in your configured IDE).

First, make sure you have no `wheels` directory in your app directory. If you do (e.g. from the last build), you need
to remove it.

**TODO**: We should change the way wheels-building tool works to not require this step.

You may still need to add some specific dependencies for your project. The dependencies must be provided as dedicated
wheel files, so the app can be installed fully offline. At the moment, the wheels building tool we provide only supports
requirements.txt file with list of dependencies. In order to build the wheels, you will need
to convert your dependencies in `pyproject.toml` to `requirements.txt`. You can do this in your app directory with
a command:

```shell
poetry export --without-hashes --format=requirements.txt > requirements.txt
```

Now that you have this file, you can build the wheels. In order to build wheels you will need to have
[`pre-commit`](https://pre-commit.com/) installed in your machine and install the configuration of your app
stored in the `.pre-commit-config.yml` file of your app. This hook script will modify your manifest file, so
make sure to run this **AFTER** creating/updating it (see above):

```shell
pre-commit run package-app-dependencies --all-files
```

This command will create a new `wheels` directory and wheel files with dependencies in it. It will also update the
manifest file with a list of dependencies pointing to the proper wheel files.

### Creating installation package

In order to create an app package that can be installed on SOAR platform, you need to create a `.tgz` tarball of
your app directory excluding the `.git` directory. Run this command from outside your app directory (or adjust the paths)

```shell
tar --exclude='.git' -zcvf MY_APP.tgz MY_APP/
```

## Installing and running the app

Now you can install the app in your SOAR platform to test how it works. You can do this by using the web interface
of the platform.

# Next steps

Now that you have a working app, you can start its development. Here's what you can check next when working
with the app you create:

- [writing the tests](/docs/testing/index.md)
- [defining action params](/docs/actions/action_params.md)
- [defining and using the action output](/docs/actions/action_outputs.md)
- [configuring the app assets](/docs/app_configuration.md)

For more advanced topics, see the [advanced apps development docs page](/docs/advanced_usage.md).
It covers old connectors porting, good practices, using the old connectors API and more.
