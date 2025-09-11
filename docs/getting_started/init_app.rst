Building an App
===============

Creating the App Skeleton
-------------------------

To build an app with the Splunk SOAR SDK, you can either start from scratch, or migrate an existing app built with the older ``BaseConnector`` framework.

.. tab-set::

    .. tab-item:: Creating a new app

        To create a new, empty app, simply run ``soarapps init`` in an empty directory.

        .. typer:: soar_sdk.cli.cli.app:init
            :prog: soarapps init
            :width: 80
            :preferred: text

        This will interactively create the basic directory structure for your app, which you can open in your editor of choice.

        .. seealso::

            See :ref:`The app structure <local_app_structure>` below for more information about the files created.

    .. tab-item:: Migrating an existing app

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

The App Structure
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

.. seealso::

    See the dedicated :ref:`app structure documentation<app-structure>` for more details on each of these files and their purposes.

The ``src`` Directory and the :ref:`app.py <app-structure-app>` File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In this directory you will develop your app source code. Apps typically start with an :ref:`app.py <app-structure-app>` file with the main module code. Larger apps can be split into multiple modules for better organization.

All apps must create one single :class:`~soar_sdk.app.App` instance. Typically, that object is created in the :ref:`app.py <app-structure-app>` file. The file which contains the :class:`~soar_sdk.app.App` instance is called the *main module* of the app. The instance must be referenced in the project's :ref:`pyproject.toml <app-structure-pyproject>` file::

    [tool.soar.app]
    main_module = "src.app:app"

Read the detailed documentation on the :ref:`app.py <app-structure-app>` file contents.

The ``logo*.svg`` Files
~~~~~~~~~~~~~~~~~~~~~~~

These files are used by the Splunk SOAR platform to present your app in the web UI. You should generally provide two versions of the logo. The regular one is used in light mode and the ``_dark`` file is used in dark mode.

PNG files are acceptable, but SVGs are preferred because they scale more easily.

The :ref:`pyproject.toml <app-structure-pyproject>` Configuration File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This file contains critical metadata about your app, like its name, license, version, and dependencies.
Learn more in the detailed documentation on the :ref:`pyproject.toml <app-structure-pyproject>` file.

.. _configuring-dev-env:

Configuring a Development Environment
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
