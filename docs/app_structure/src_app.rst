.. _app-structure-app:

``src/app.py``
==============

This document will dive deeper into the initial structure of the ``app.py`` file when starting working with Apps.

The file consists of a few main parts:

1. :ref:`Logger initialization <app-structure-logger-init>`
2. :ref:`Asset definition <app-structure-asset-def>`
3. :ref:`App initialization <app-structure-app-init>`
4. :ref:`Actions definitions <app-structure-actions-def>`
5. :ref:`App CLI invocation <app-structure-app-cli>`

Here's an example ``app.py`` file which uses a wide variety of the features available in the SDK:

.. literalinclude:: ../../tests/example_app/src/app.py
   :language: python
   :linenos:

Components of the ``app.py`` file
---------------------------------

Let's dive deeper into each part of the ``app.py`` file above:

.. _app-structure-logger-init:

Logger initialization
~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tests/example_app/src/app.py
   :caption: Logger initialization
   :language: python
   :lineno-match:
   :start-at: import getLogger
   :end-at: getLogger()

The SDK provides a logging interface via the :func:`~soar_sdk.logging.getLogger` function. This is a standard Python logger which is pre-configured to work with either the local CLI or the SOAR platform. Within the platform,

- ``logger.debug()`` and ``logger.warning()`` messages are written to the ``spawn.log`` file at ``DEBUG`` level.
- ``logger.error()`` and ``logger.critical()`` messages are written to the ``spawn.log`` file at ``ERROR`` level.
- ``logger.info()`` messages are sent to the SOAR platform as persistent action progress messages, visible in the UI.
- ``logger.progress()`` messages are sent to the SOAR platform as transient action progress messages, visible in the UI, but overwritten by subsequent progress messages.

When running locally via the CLI, all log messages are printed to the console, in colors corresponding to their log level.

.. _app-structure-asset-def:

Asset definition
~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: Asset definition
    :language: python
    :lineno-match:
    :pyobject: Asset

Apps should define an asset class to hold configuration information for the app. The asset class should be a `pydantic model <https://docs.pydantic.dev/1.10/usage/models/#basic-model-usage>`_ that inherits from :class:`~soar_sdk.asset.BaseAsset` and defines the app's configuration fields. Fields requiring metadata should be defined using an instance of :func:`~soar_sdk.asset.AssetField`. The SDK uses this information to generate the asset configuration form in the SOAR platform UI.

.. _app-structure-app-init:

App initialization
~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: App initialization
    :language: python
    :lineno-match:
    :start-at: app = App(
    :end-at: )

This is how you initialize the basic :class:`~soar_sdk.app.App` instance. The app object will be used to register actions, views, and/or webhooks. Keep in mind this object variable and its path are referenced by :ref:`pyproject.toml <app-structure-pyproject>` so the SOAR platform knows where the app instance is provided.

.. _app-structure-actions-def:

Actions definitions
~~~~~~~~~~~~~~~~~~~

action anatomy
^^^^^^^^^^^^^^

Actions are defined as standalone functions, which typically take arguments:

- ``params`` - a `pydantic model <https://docs.pydantic.dev/1.10/usage/models/#basic-model-usage>`_ class inheriting from :class:`~soar_sdk.params.Params`.
- ``soar`` - Optional, an instance of the :class:`~soar_sdk.abstract.SOARClient` implementation providing APIs for interacting with the Splunk SOAR platform.
- ``asset`` - Optional, an instance of the app's asset class, populated with the asset configuration for the current action run.

The action's type hints are required by the SDK; the type hint for the ``params`` argument, as well as the action's return type (which must be a `pydantic model <https://docs.pydantic.dev/1.10/usage/models/#basic-model-usage>`_ class inheriting from :class:`~soar_sdk.action_results.ActionOutput`), are used to generate the action's datapaths in the manifest.


Similarly, the action function's docstring is used to generate the action's description in the manifest and the SOAR platform UI. Also, the type hints for the ``soar`` and ``asset`` arguments are used at runtime to dynamically inject the appropriate arguments when the action is executed.

test connectivity action
^^^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: Test connectivity action definition
    :language: python
    :lineno-match:
    :pyobject: test_connectivity

All apps must register exactly one ``test_connectivity`` action in order to be considered valid by Splunk SOAR. This action takes no parameters, and is used to verify that the app and its associated asset configuration are working correctly. Running ``test connectivity`` on the Splunk SOAR platform should answer the questions:

- Can the app connect to the external service?
- Can the app authenticate with the external service?
- Does the app have the necessary permissions to perform its actions?

A successful ``test connectivity`` action should return ``None``, and a failure should raise an :class:`~soar_sdk.exceptions.ActionFailure` with a descriptive error message.

on poll action
^^^^^^^^^^^^^^

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: on poll action definition
    :language: python
    :lineno-match:
    :pyobject: on_poll

``on poll`` is another special action that apps may choose to implement. This action always takes an :class:`~soar_sdk.params.OnPollParams` instance as its parameter. If defined, this action will be called in order to ingest new data into the Splunk SOAR platform. The action should yield  :class:`~soar_sdk.models.container.Container` and/or :class:`~soar_sdk.models.artifact.Artifact` instances representing the new data to be ingested. The SDK will handle actually creating the containers and artifacts in the platform.

generic action
^^^^^^^^^^^^^^

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: Generic action definition
    :language: python
    :lineno-match:
    :pyobject: http_action

Apps may define a special "generic HTTP" action, which can be used to interact with the underlying external service's REST API directly. Having this action available can be useful when there are parts of the REST API that don't have dedicated actions implemented in the app. These

We create an action by decorating a function with the ``app.action`` decorator. The default ``action_type``
is ``generic``, so usually you will not have to provide this argument for the decorator. This is not the
case for the ``test`` action type though, so we provide this type here explicitly.

custom actions
^^^^^^^^^^^^^^

Actions can be registered one of two ways:

.. tab-set::

    .. tab-item:: ``@app.action()``

        Using the :func:`~soar_sdk.app.App.action` decorator to decorate a standalone function.

        .. literalinclude:: ../../tests/example_app/src/app.py
            :caption: decorated action definition
            :language: python
            :lineno-match:
            :pyobject: generator_action

    .. tab-item:: ``app.register_action()``

        Using the :func:`~soar_sdk.app.App.register_action` method to register a function which may be defined in another module.

        .. literalinclude:: ../../tests/example_app/src/app.py
            :caption: registered action definition
            :language: python
            :lineno-match:
            :start-at: import render_reverse_string
            :end-at: )

The two methods are functionally equivalent. The decorator method is often more convenient for simple actions, while the registration method may be preferable for larger apps where actions are defined in separate modules. Apps may use either or both methods to register their actions.

.. _app-structure-app-cli:

App CLI invocation
~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: App CLI invocation
    :language: python
    :lineno-match:
    :start-at: if __name__

A generic invocation to the app's :func:`~soar_sdk.app.App.cli` method, which enables running the app actions directly from command line. The app template created by ``soarapps init`` includes this snippet by default, and it is recommended to keep it in order to facilitate local testing and debugging of your app actions.
