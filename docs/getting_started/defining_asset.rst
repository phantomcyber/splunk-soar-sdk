Defining Your App's Asset Configuration
=======================================


Much of the functionality of a Splunk SOAR app depends on its ability to connect to external systems. This is done using an asset configuration, which provides the necessary connection details and credentials.

Like much of the definitions for objects in a Splunk SOAR app, the asset configuration is defined using `Pydantic models <https://docs.pydantic.dev/1.10/usage/models/#basic-model-usage>`_. The power of Pydantic models allows you to define complex data structures with validation and serialization capabilities, in a way where your code editor will be able to provide autocompletions and type checking.

.. note::
    Users familiar with the ``BaseConnector`` style of Splunk SOAR apps may remember defining asset configuration with JSON. The Splunk SOAR SDK prefers to define all configuration in Python, and generate the JSON schema automatically. This ensures that the code and configuration are always in sync, and provides developers with significantly more useful editor support.

In the case of assets, these models must be subclasses of :class:`~soar_sdk.app.Asset`. An example Asset definition looks something like this:

.. literalinclude:: ../../tests/example_app/src/app.py
    :caption: Asset definition
    :language: python
    :lineno-match:
    :pyobject: Asset

.. seealso::

    For more information on how to define an asset configuration, see the :ref:`App Structure <app-structure-asset-def>` documentation.


Finally, in order to register the asset configuration with the app, it must be provided to the :class:`~soar_sdk.app.App` instance as the ``asset_cls`` parameter. For example::

    app = App(
        name="My App",
        description="An example app",
        version="1.0.0",
        asset_cls=Asset,  # <--- Asset class provided here
    )
