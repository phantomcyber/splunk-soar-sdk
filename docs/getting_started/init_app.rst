Getting started with your app
=============================

.. tab-set::

    .. tab-item:: Creating a new app

        Creating a new app
        ------------------

        To create a new, empty app, simply run ``soarapps init`` in an empty directory.

        .. typer:: soar_sdk.cli.cli.app:init
            :prog: soarapps init
            :width: 80
            :preferred: text

        This will interactively create the basic directory structure for your app, which you can open in your editor of choice.

        See :ref:`The app structure <local_app_structure>` below for more information about the files created.

    .. tab-item:: Migrating an existing app

        Migrating an existing app
        -------------------------

        To migrate an existing app, ``myapp``, that was written in the old ``BaseConnector`` framework, run ``soarapps convert myapp``.

        .. typer:: soar_sdk.cli.cli.app:convert
            :prog: soarapps convert
            :width: 80
            :preferred: text

        This will create a new SDK app, migrating the following aspects of your existing app:

        - Asset configuration parameters
        - Action names, descriptions, and other metadata
        - Action parameters and outputs

        You will need to re-implement the code for each of your actions yourself.

        Automatic migration is not yet supported for the following features, and you will need to migrate these yourself:

        - Custom views
        - Webhook handlers
        - Custom REST handlers (must be converted to webhooks, as the SDK does not support Custom REST)
        - Initialization code
        - Action summaries

.. _local_app_structure:

The app structure
-----------------

Running the ``soarapps init`` or ``soarapps convert`` commands will create the following directory structure::

    my_app/
    ├─ src/
    │  ├─ __init__.py
    │  ├─ app.py
    ├─ .pre-commit-config.yaml
    ├─ logo.svg
    ├─ logo_dark.svg
    ├─ pyproject.toml

See the dedicated :ref:`app structure documentation<app-structure>` for more details on each of these files and their purposes.

The ``src`` directory and the :ref:`app.py <app-structure-app>` file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In this directory you will develop your app source code. Apps typically start with an :ref:`app.py <app-structure-app>` file with the main module code. Larger apps can be split into multiple modules for better organization.

All apps must create one single :class:`~soar_sdk.app.App` instance. Typically, that object is created in the :ref:`app.py <app-structure-app>` file. The file which contains the :class:`~soar_sdk.app.App` instance is called the *main module* of the app. The instance must be referenced in the project's :ref:`pyproject.toml <app-structure-pyproject>` file::

    [tool.soar.app]
    main_module = "src.app:app"

Read the detailed documentation on the :ref:`app.py <app-structure-app>` file contents.

The ``logo*.svg`` files
~~~~~~~~~~~~~~~~~~~~~~~

These files are used by the Splunk SOAR platform to present your app in the web UI. You should generally provide two versions of the logo. The regular one is used in light mode and the ``_dark`` file is used in dark mode.

PNG files are acceptable, but SVGs are preferred because they scale more easily.

The :ref:`pyproject.toml <app-structure-pyproject>` configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This file contains critical metadata about your app, like its name, license, version, and dependencies.
Learn more in the detailed documentation on the :ref:`pyproject.toml <app-structure-pyproject>` file.

.. _configuring-dev-env:

Configuring a development environment
--------------------------------------

After creating an app skeleton, it's time to set up a development environment.

First, it's recommended to create a Git repository::

    git init

In the app directory, install the `pre-commit <https://pre-commit.com/>`_ hooks defined by :ref:`pre-commit-config.yaml <app-structure-pre-commit>`::

    pre-commit install

Then, set up the environment using `uv <https://docs.astral.sh/uv/>`_. It will set up the virtual environment and install necessary dependencies. Add the SDK as a dependency::

    uv add splunk-soar-sdk
    uv sync

It's also useful to activate the virtual environment created by uv, so that shell commands run in context of the app's environment::

    source .venv/bin/activate

Creating your first action
---------------------------

The app should already have an ``app`` object defined in the ``app.py`` file. It will likely need to define an ``Asset`` model to be useful. Read more on that in the :ref:`App Configuration <asset-configuration-label>` documentation.

All actions are defined as standalone functions, which are then registered with the app.
Actions can be registered in multiple ways. See :ref:`Defining actions <app-structure-actions-def>` and/or :ref:`Action API Reference <api_ref_key_methods_label>` for more information.

The simplest action to create would look like this::

    @app.action()
    def my_action(params: Params, asset: BaseAsset) -> ActionOutput:
        """This is the first custom action in the app. It doesn't really do anything yet."""
        return ActionOutput()

Let's break down this example to explain what happens here.

:func:`~soar_sdk.app.App.action` decorator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    @app.action()
    def my_action(...):

The decorator registers new action functions against :class:`~soar_sdk.app.App` instances. It is responsible for many things related to running the app under the hood. Here are some things it takes care of:

- registers new action functions, so they are invoked when running the app in SOAR platform
- sets the configuration values for the action (which can be defined by providing extra parameters to the decorator)
- ensures that the action name (by default, derived from the function name) is unique within the app
- checks if the action params are provided, valid and of the proper type
- ensures that the action output type is provided via return type annotation, and is valid
- inspects action argument types and validates them

For more information about action registration, see the :ref:`API Reference <api_ref_key_methods_label>`.

The action declaration
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def my_action(params: Params, asset: BaseAsset) -> ActionOutput:

``my_action`` is the identifier of the action, and is used to derive the action's name (``my action``). This name will be used in the Splunk SOAR platform UI, and will be added to the app's generated manifest at packaging time.

Each action may accept and define ``params`` and ``asset`` arguments with proper type hints.

The ``params`` argument should always be of a type inherited from :class:`~soar_sdk.params.Params`. Read more on defining action params in the :ref:`API Reference <action-param-label>`. If an action takes no parameters, it's fine to use the ``Params`` base class here.

The ``asset`` argument contains an instance of the app's asset configuration, which is discussed further in the :ref:`App Configuration <asset-configuration-label>` documentation. It should be of a type that inherits from :class:`~soar_sdk.asset.BaseAsset`, and should be the same type that is specified as the ``asset_cls`` of the app.

Actions must have a return type that resolves to a type which extends from :class:`~soar_sdk.action_results.ActionOutput`. This is discussed further in the :ref:`Action Outputs <action-output-label>` documentation. The return type must be hinted.

.. seealso::

    For more advanced use cases, an action's return type can be a ``Coroutine`` that resolves to an :class:`~soar_sdk.action_results.ActionOutput`; or a ``list``, ``Iterator`` or ``AsyncGenerator`` that yields multiple :class:`~soar_sdk.action_results.ActionOutput` objects.

The action docstring
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

        """This is the first custom action in the app. It doesn't really do anything yet."""

All actions should have a docstring. Beyond the general best practice it represents, the docstring is (by default) used by the :func:`~soar_sdk.app.App.action` decorator to generate the action description for the app documentation in Splunk SOAR.

The description should be kept short and simple, explaining what the action does.

The action result
~~~~~~~~~~~~~~~~~

.. code-block:: python

        return ActionOutput()

Each successful action run must return at least one action result.
Actions can fail gracefully by raising an :class:`~soar_sdk.exceptions.ActionFailure` exception. Other exceptions will be treated as unexpected errors.

The given example action simply returns the :class:`~soar_sdk.action_results.ActionOutput` base class, as it does not yet generate any results.

Read more on action results and outputs in the :ref:`Action Outputs <action-output-label>` section of the API Reference.

.. _testing-and-building-app:

Testing and building the app
----------------------------

Running from the command line
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can run any of your app's actions directly in your CLI, without installing a full copy of SOAR. Simply invoke the Python file that contains your app::

    python src/app.py action my-action -p test_params.json -a test_asset.json

You should provide a parameters file (``-p``) which contains the JSON-encoded parameters for your action. The asset file (``-a``) contains the asset config in JSON format.

This command will run your action on your local machine, and print its output to the command line.

Building an app package
~~~~~~~~~~~~~~~~~~~~~~~

Run ``soarapps package build`` to generate an app package. By default, this creates ``<appname>.tgz`` in the root directory of your app.

This package contains all the code and metadata for your app. It also contains all the dependency wheels for your app, which are sourced from the PyPI CDN based on ``uv.lock``.

Because of this, you should ensure that your ``uv.lock`` is always up to date.

Installing and running the app
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now you can install the app in your SOAR platform to test how it works. You can do this by using the web interface of the platform.

You can also do this from the command line::

    soarapps package install myapp.tgz soar.example.com

Getting help
------------

If you need help, please file a GitHub issue at https://github.com/phantomcyber/splunk-soar-sdk/issues.

Next steps
----------

Now that you have a working app, you can start its development. Here's what you can check next when working with the app you create:

- :ref:`Asset Configuration <asset-configuration-label>`
- :ref:`Action Parameters <action-param-label>`
- :ref:`Action Outputs <action-output-label>`
