
# Getting started

In this section we will guide you through the basic process of creating your first draft of the SOAR App.

## Actions philosophy

Apps (aka Connectors) in Splunk SOAR are extensions that enrich the platform functionality. Each app provides a new set of actions that can be used for the security investigation (also automated one, when used in playbooks). Usually, a single app adds actions for one specific tool or 3rd party service (e.g. whois lookup or geolocation).

When building your app, you will focus on implementing the actions like sending data to the external service
or updating the containers on SOAR platform.

This SDK is a set of tools to build, test and run your own app that will extend the SOAR installation by implementing
actions.

# Your first app

The following guide will get you through the process of building your first app, explaining
its crucial components and functionality.

## Setting up your machine

You will need a Mac or Linux machine. Windows is not supported.

First, install some necessary tools:
- Git
- [uv](https://docs.astral.sh/uv/): the Python version and environment manager used by the SDK

Next, install Python 3.9 and 3.13. These are the two versions currently supported for SOAR apps:

```shell
uv python install 3.9
uv python install 3.13
```

Finally, install the SOAR SDK as a command-line tool:

```shell
uv tool install splunk-soar-sdk
```

It may also be helpful to install `ruff` and `pre-commit`, as these are used often when building SOAR apps:
```shell
uv tool install ruff
uv tool install pre-commit
```

## Creating a new app

To create a new, empty app, simply run:

```shell
soarapps init
```

This will create the basic directory structure for your app, which you can open in your editor. See {ref}`The app structure <app-structure>` below for more information.

## Migrating an existing app

To migrate an existing app, `myapp`, that was written in the old `BaseConnector` framework, run:

```shell
soarapps convert myapp
```

The conversion script will create a new SDK app, migrating the following aspects of your existing app:

- Asset configuration parameters
- Action names, descriptions, and other metadata
- Action parameters and outputs

You will need to re-implement the code for each of your actions yourself.

Automatic migration is not yet supported for the following features, and you will need to migrate these yourself:

- Custom views
- Webhook handlers
- Custom REST handlers (must be converted to webhooks, as the SDK does not support Custom REST)

## The app structure

Running the `soarapps init` or `soarapps convert` commands will create the following directory structure:

```shell

my_app/
├─ src/
│  ├─ __init__.py
│  ├─ app.py
├─ .pre-commit-config.yaml
├─ logo.svg
├─ logo_dark.svg
├─ pyproject.toml
```

We describe and explain each of the files in full in the dedicated {ref}`documentation pages about the app structure <app-structure>`.

For now, let's shortly go over each of the components in the structure, so we can create our first action.

### The `src` directory and the `app.py` file

In this directory you will develop your app source code. We typically place here the `app.py` file
with the main module code. Keep in mind you can always add more python modules to this directory and import
them in the `app.py` file to create cleaner maintainable code.

In the `app.py` file we typically create the `App` instance and define actions and provide its implementation.
This module will be used in our `pyproject.toml` app configuration to point the `app` object as `main_module` for
use in SOAR platform when running actions.

Read the detailed documentation on the {ref}`app.py <app-structure-app>` file contents

Note that the `test_connectivity` action is mandatory for each app. It is used when installing the app in
the SOAR platform and checked usually when a new asset is added for the app. This is why it is always provided
in the app scratch files.

### The `logo*.svg` files

These files are used by SOAR platform to present your application in the web UI. You should generally provide
two versions of the logo. The regular one is used for light mode and the `_dark` file is used for the dark mode.

PNG files are also acceptable, but SVGs are preferred because they scale more easily.

### `pyproject.toml` configuration file

This file defines the app development parameters, dependencies, and also configuration data for the app.

In this file you will define poetry dependencies (including this SDK) and basic information like the name
of the app, its version, description, authors, and other params.

Read the detailed documentation on the {ref}`pyproject.toml <app-structure-pyproject>` file contents

(configuring-enviornment)=
## Configuring the environment

Once you have your starting app file structure, you will need to set up your app development environment.

First, set up a Git repository:

```shell
git init
```

In your app directory, install the pre-commit hooks:

```shell
pre-commit install
```

Then you need to set up the environment using uv. It will set up the virtual environment and install
necessary dependencies. You should also add the SDK to your project:

```shell
uv add splunk-soar-sdk
uv sync
```

It's also useful to activate the virtual environment created by uv, so that all your shell commands run in context of your app:
```shell
source .venv/bin/activate
```

## Creating your first action

Your app should already have the `app` object instance created in the `app.py` file. In the future you will
initialize it with extra arguments, like the asset configuration, to specify the asset data. You can read more on
how to initialize the app in the {ref}`App Configuration <asset-configuration-label>` documentation.

For now let's focus on creating a very simple action and see the basics of its structure. You should already have
one action defined in your `app.py` file called `test_connectivity` which must be created in every app. You can check
how it is constructed. Our first action will be very similar to it.

The `app` instance provides the `action` decorator which is used to turn your python functions into SOAR App actions.

Here's the code of the simplest action you can create:

```python
@app.action()
def my_action(params: Params, asset: BaseAsset) -> ActionOutput:
    """This is the first custom action in the app. It doesn't really do anything yet."""
    return ActionOutput()
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

For more information about the `App.action` decorator, see the {ref}`API Reference <api_ref_key_methods_label>`.

### The action declaration

```python
def my_action(params: Params, asset: BaseAsset) -> ActionOutput:
```

`my_action` is the identifier of the action and as such it will be visible later in the SOAR platform.
`App.action` decorator automatically converts this to _"my action"_ string name that will be used when generating
the app Manifest file and the documentation.

Each action should accept and define `params` and `asset` arguments with proper typehints.

The `params` argument should always be of the class type inherited from `soar_sdk.params.Params`.
You can read more on defining action params in the {ref}`API Reference <action-param-label>`.
If your action takes no parameters, it's fine to use the `Params` base class here.

The `asset` argument contains your asset configuration, which is discussed further in the {ref}`App Configuration <asset-configuration-label>` documentation. It should be of a type that inherits from `soar_sdk.asset.BaseAsset`, and should be the same type that is specified as the `asset_cls` of your app.

Your action must have a return type that extends from `soar_sdk.action_results.ActionOutput`. This is discussed further in the {ref}`Action Outputs <action-output-label>` documentation. The return type must be hinted.

For more advanced use cases, your return type can be a Coroutine that resolves to an ActionOutput; or a list, Iterator or AsyncGenerator that yields multiple ActionOutputs.

### The action description docstring

```python
    """This is the first custom action in the app. It doesn't really do anything yet."""
```

You should always provide the docstring for your action. It makes your code easier to understand and maintain, but
also, the docstring is (by defualt) used by the `App.action` decorator to generate the action description for the
app documentation in SOAR platform.

The description should be kept short and simple, explaining what the action does.

### The action result

```python
    return ActionOutput()
```

Each action must return at least one action result. While you can create multiple instances of the action result
and pass more than one values, the one that is most important is the general action result.

Prior to SDK, the connectors had to define and create their own `ActionResult` instances. This is simplified now
in SDK. If your action succeeds, it should return an instance of your output class. If it fails, it should raise an exception.

Our example action simply returns the `ActionOutput` base class, as it does not yet generate any results.

Read more on action results and outputs in the {ref}`Action Outputs <action-output-label>` section of the API Reference.

As you can see, this simple action is taking bare `Params` object, so with no defined params and simply returns
the result of successful run.

(testing-and-building-app)=
## Testing and building the app

### Running from the command line

You can run any of your app's actions directly in your CLI, without installing a full copy of SOAR.
Simply invoke the Python file that contains your app:

```python
python src/app.py action my-action -p test_params.json -a test_asset.json
```

You should provide a parameters file (`-p`) which contains the JSON-encoded parameters for your action.
The asset file (`-a`) contains the asset config in JSON format.

This command will run your action on your local machine, and print its output to the command line.

### Building an app package

Run `soarapps package build` to generate an app package.
By default, this creates `<appname>.tgz` in the root directory of your app.

This package contains all the code and metadata for your app.
It also contains all the dependency wheels for your app, which are sourced from the PyPI CDN based on `uv.lock`.

Because of this, you should ensure that your `uv.lock` is always up to date.

## Installing and running the app

Now you can install the app in your SOAR platform to test how it works. You can do this by using the web interface
of the platform.

You can also do this from the command line:

```shell
soarapps package install myapp.tgz soar.example.com
```

# Getting help

If you need help, please file a GitHub issue at <https://github.com/phantomcyber/splunk-soar-sdk/issues>.

# Next steps

Now that you have a working app, you can start its development. Here's what you can check next when working
with the app you create:

- {ref}`Asset Configuration <asset-configuration-label>`
- {ref}`Action Parameters <action-param-label>`
- {ref}`Action Outputs <action-output-label>`
