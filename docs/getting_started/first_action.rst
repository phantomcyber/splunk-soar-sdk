Creating Your First Actions
===========================

All actions are defined as standalone functions, which are then registered with the :class:`~soar_sdk.app.App` object. Further, all apps are expected to implement a special ``test connectivity`` action, which is used to verify that the app can connect and authenticate to its external service.

The ``test connectivity`` Action
--------------------------------

Every app must implement a ``test connectivity`` action. This action takes no parameters, and is used to verify that the app and its associated asset configuration are working correctly. Running ``test connectivity`` on the Splunk SOAR platform should answer the questions:

- Can the app connect to the external service?
- Can the app authenticate with the external service?
- Does the app have the necessary permissions to perform its actions?

For example:

.. code-block:: python

    @app.test_connectivity()
    def test_connectivity(asset: Asset) -> None:
        logger.info("Testing connectivity")

        with httpx.Client() as client:
            response = client.get("https://example.com/api/health", headers={
                "Authorization": f"Bearer {asset.api_token}"
            })
            if not response.ok:
                raise ActionFailure(
                    f"Connectivity test failed with status code {response.status_code}"
                )

        logger.info("Connectivity test succeeded")

Your First Action
-----------------

Actions can be registered in multiple ways, with advantages and trade-offs to each. For a smaller app, the easiest method is to use the :func:`~soar_sdk.app.App.action` decorator directly on a function.

.. seealso::

    See :ref:`Defining actions <app-structure-actions-def>` and/or :ref:`Action API Reference <api_ref_key_methods_label>` for more information.

The simplest action to create would look like this::

    @app.action()
    def my_action(params: Params, asset: BaseAsset) -> ActionOutput:
        """This is the first custom action in the app. It doesn't really do anything yet."""
        return ActionOutput()

Let's break down this example to explain what happens here.

:func:`~soar_sdk.app.App.action` Decorator
------------------------------------------

.. code-block:: python

    @app.action()
    def my_action(...):

The decorator registers new action functions against :class:`~soar_sdk.app.App` instances. It is responsible for many things related to running the app under the hood. Here are some things it takes care of:

- registers new action functions, so they are invoked when running the app in Splunk SOAR platform
- sets the configuration values for the action (which can be defined by providing extra parameters to the decorator)
- ensures that the action name (by default, derived from the function name) is unique within the app
- checks if the action params are provided, valid and of the proper type
- ensures that the action output type is provided via return type annotation, and is valid
- inspects action argument types and validates them

.. seealso::

    For more information about action registration, see the :ref:`App structure <app-structure-actions-def>` or :ref:`API Reference <api_ref_key_methods_label>` docs.

The Action Declaration
----------------------

.. code-block:: python

    def my_action(params: Params, asset: BaseAsset) -> ActionOutput:

``my_action`` is the identifier of the action, and is used to derive the action's name (``my action``). This name will be used in the Splunk SOAR platform UI, and will be added to the app's generated manifest at packaging time.

Each action may accept and define ``params`` and ``asset`` arguments with proper type hints.

The ``params`` argument should always be the first argument, and of a type inherited from :class:`~soar_sdk.params.Params`. If an action takes no parameters, it's fine to use the ``Params`` base class here.

.. seealso::

    Read more on defining action params in the :ref:`API Reference <action-param-label>` or :ref:`App structure <app-structure-actions-def>` docs.

The ``asset`` argument contains an instance of the app's asset configuration. It should be the same type that is specified as the ``asset_cls`` of the app.

Actions must have a return type that resolves to a type which extends from :class:`~soar_sdk.action_results.ActionOutput`. This is discussed further in the :ref:`Action Outputs <action-output-label>` and :ref:`App structure <app-structure-actions-def>` docs. The return type must be hinted.

The Action Docstring
--------------------

.. code-block:: python

        """This is the first custom action in the app. It doesn't really do anything yet."""

All actions should have a docstring. Beyond the general best practice it represents, the docstring is (by default) used by the SDK to generate the action description for the app documentation in Splunk SOAR.

The description should be kept short and simple, explaining what the action does.

The Action Result
-----------------

.. code-block:: python

        return ActionOutput()

Each successful action run must return at least one action result.
Actions can fail gracefully by raising an :class:`~soar_sdk.exceptions.ActionFailure` exception. Other exceptions will be treated as unexpected errors.

The given example action simply returns the :class:`~soar_sdk.action_results.ActionOutput` base class, as it does not yet generate any results.

.. seealso::

    Read more on action results and outputs in the :ref:`API Reference <action-output-label>` or :ref:`App structure <app-structure-action-returns>` docs.
