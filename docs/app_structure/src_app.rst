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

Components of the ``app.py`` File
---------------------------------

Let's dive deeper into each part of the ``app.py`` file above:

.. _app-structure-logger-init:

Logger Initialization
~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tests/example_app/src/app.py
   :caption: Logger initialization
   :language: python
   :lineno-match:
   :start-at: import getLogger
   :end-at: getLogger()

The SDK provides a logging interface via the :func:`~soar_sdk.logging.getLogger` function. This is a standard Python logger which is pre-configured to work with either the local CLI or the Splunk SOAR platform. Within the platform,

- ``logger.debug()`` and ``logger.warning()`` messages are written to the ``spawn.log`` file at ``DEBUG`` level.
- ``logger.error()`` and ``logger.critical()`` messages are written to the ``spawn.log`` file at ``ERROR`` level.
- ``logger.info()`` messages are sent to the Splunk SOAR platform as persistent action progress messages, visible in the UI.
- ``logger.progress()`` messages are sent to the Splunk SOAR platform as transient action progress messages, visible in the UI, but overwritten by subsequent progress messages.

When running locally via the CLI, all log messages are printed to the console, in colors corresponding to their log level.

.. _app-structure-asset-def:

Asset Definition
~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: Asset definition
    :language: python
    :lineno-match:
    :pyobject: Asset

Apps should define an asset class to hold configuration information for the app. The asset class should be a `pydantic model <https://docs.pydantic.dev/1.10/usage/models/#basic-model-usage>`_ that inherits from :class:`~soar_sdk.asset.BaseAsset` and defines the app's configuration fields. Fields requiring metadata should be defined using an instance of :func:`~soar_sdk.asset.AssetField`. The SDK uses this information to generate the asset configuration form in the Splunk SOAR platform UI.

.. _app-structure-app-init:

App Initialization
~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: App initialization
    :language: python
    :lineno-match:
    :start-at: app = App(
    :end-at: )

This is how you initialize the basic :class:`~soar_sdk.app.App` instance. The app object will be used to register actions, views, and/or webhooks. Keep in mind this object variable and its path are referenced by :ref:`pyproject.toml <app-structure-pyproject>` so the Splunk SOAR platform knows where the app instance is provided.

.. _app-structure-actions-def:

Action Definitions
~~~~~~~~~~~~~~~~~~

Actions are defined as standalone functions, with a few important rules and recommendations.

Action Metadata
^^^^^^^^^^^^^^^

Action definition carry with them important metadata which is used by the Splunk SOAR platform to present the action in the UI, and to generate the app's manifest. Often, this metadata can be derived automatically from the action function's signature:

- The action's "identifier" is, by default, the name of the action function (e.g. ``my_action``).
- The action's "name" is, by default, the action function's name with spaces instead of underscores (e.g. ``my action``).
- The action's "description" is, by default, the action function's docstring.
- The action's "type" is, by default, ``generic`` unless the action is one of the reserved names like ``test connectivity`` or ``on poll``.

.. note::
    By convention, action names should be lowercase, with 2-3 words. Keep action names short but descriptive, and avoid using the name of the app or external service in action names. Where feasible, it's recommended to consider reusing action names across different apps (e.g. ``get email``) to provide a more consistent user experience.

.. _app-structure-actions-args:

Action Arguments
^^^^^^^^^^^^^^^^

There is a magic element, similar to `pytest fixtures <https://docs.pytest.org/en/stable/how-to/fixtures.html#requesting-fixtures>`_, in the action arguments. The type hints for the argument definitions of an action function are critical to this mechanism. The rules are as follows:

- The first positional argument of an action function must be the ``params`` argument, and its type hint must be a `Pydantic model <https://docs.pydantic.dev/1.10/usage/models/#basic-model-usage>`_ inheriting from :class:`~soar_sdk.params.Params`. The position and type of this argument are required. The name ``params`` is a convention, but not strictly required.
- If an action function has any argument named ``soar``, at runtime the SDK will provide an instance of a :class:`~soar_sdk.abstract.SOARClient` implementation as that argument, which is already authenticated with Splunk SOAR. The type hint for this argument should be :class:`~soar_sdk.abstract.SOARClient`.
- If an action function has any argument named ``asset``, at runtime the SDK will provide an instance of the app's asset class, populated with the asset configuration for the current action run. The type hint for this argument should be the app's asset class.

.. note::
    The special actions which define their own decorators have stricter rules about the type of the ``params`` argument. For example, the ``on poll`` action must take an :class:`~soar_sdk.params.OnPollParams` instance as its ``params`` argument, and ``test connectivity`` must take no ``params`` argument at all.

.. _app-structure-action-returns:

Action Returns
^^^^^^^^^^^^^^

An action's return type annotation is critical for the Splunk SOAR platform to understand, via datapaths, what an action's output looks like. In practice, this means that you must define a class inheriting from :class:`~soar_sdk.action_results.ActionOutput` to represent the action's output, and then return an instance of that class from your action function:

.. code-block:: python

    from soar_sdk.action_results import ActionOutput

    class MyActionOutput(ActionOutput):
        field1: str
        field2: int

    @app.action()
    def my_action(params: MyActionParams) -> MyActionOutput:
        # action logic here
        return MyActionOutput(field1="value", field2=42)

Advanced Return Types
*********************

For more advanced use cases, an action's return type can be a ``list``, ``Iterator``, or ``AsyncGenerator`` that yields multiple :class:`~soar_sdk.action_results.ActionOutput` objects:

.. tab-set::
    .. tab-item:: ``list``

        .. code-block:: python

            @app.action()
            def my_action_list(params: MyActionParams) -> list[MyActionOutput]:
                # action logic here
                return [
                    MyActionOutput(field1="value1", field2=1),
                    MyActionOutput(field1="value2", field2=2)
                ]

    .. tab-item:: ``Iterator``

        .. code-block:: python

            from typing import Iterator

            @app.action()
            def my_action_iterator(params: MyActionParams) -> Iterator[MyActionOutput]:
                # action logic here
                yield MyActionOutput(field1="value1", field2=1)
                yield MyActionOutput(field1="value2", field2=2)


    .. tab-item:: ``AsyncGenerator``

        .. code-block:: python

            from typing import AsyncGenerator

            @app.action()
            async def my_action_async_generator(
                params: MyActionParams,
                asset: Asset,
            ) -> AsyncGenerator[MyActionOutput]:
                async with client = httpx.AsyncClient() as client:
                    async for i in range(10):
                        response = await client.get(
                            f"{asset.base_url}/data",
                            params={"page": i}
                        )
                        yield MyActionOutput(**response.json())


``test connectivity`` Action
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: Test connectivity action definition
    :language: python
    :lineno-match:
    :pyobject: test_connectivity

All apps must register exactly one ``test connectivity`` action in order to be considered valid by Splunk SOAR. This action takes no parameters, and is used to verify that the app and its associated asset configuration are working correctly. Running ``test connectivity`` on the Splunk SOAR platform should answer the questions:

- Can the app connect to the external service?
- Can the app authenticate with the external service?
- Does the app have the necessary permissions to perform its actions?

A successful ``test connectivity`` action should return ``None``, and a failure should raise an :class:`~soar_sdk.exceptions.ActionFailure` with a descriptive error message.

``on poll`` Action
^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: on poll action definition
    :language: python
    :lineno-match:
    :pyobject: on_poll

``on poll`` is another special action that apps may choose to implement. This action always takes an :class:`~soar_sdk.params.OnPollParams` instance as its parameter. If defined, this action will be called in order to ingest new data into the Splunk Splunk SOAR platform. The action should yield  :class:`~soar_sdk.models.container.Container` and/or :class:`~soar_sdk.models.artifact.Artifact` instances representing the new data to be ingested. The SDK will handle actually creating the containers and artifacts in the platform.

Make Request Action
^^^^^^^^^^^^^^

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: Make request action definition
    :language: python
    :lineno-match:
    :pyobject: http_action

Apps may define a special "make request" action, which can be used to interact with the underlying external service's REST API directly. Having this action available can be useful when there are parts of the REST API that don't have dedicated actions implemented in the app.

We create an action by decorating a function with the ``app.action`` decorator. The default ``action_type``
is ``generic``, so usually you will not have to provide this argument for the decorator. This is not the
case for the ``test`` action type though, so we provide this type here explicitly.

Custom Actions
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
            :start-at: "actions.reverse_string:render_reverse_string_view"
            :end-at: )

The two methods are functionally equivalent. The decorator method is often more convenient for simple actions, while the registration method may be preferable for larger apps where actions are defined in separate modules. Apps may use either or both methods to register their actions.

.. _app-structure-app-cli:

App CLI Invocation
~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: App CLI invocation
    :language: python
    :lineno-match:
    :start-at: if __name__

A generic invocation to the app's :func:`~soar_sdk.app.App.cli` method, which enables running the app actions directly from command line. The app template created by ``soarapps init`` includes this snippet by default, and it is recommended to keep it in order to facilitate local testing and debugging of your app actions.
