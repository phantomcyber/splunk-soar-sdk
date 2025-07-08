API Reference
=============

This section documents the public API of the Splunk SOAR SDK.

Core Classes
------------

App
~~~

.. autoclass:: soar_sdk.app.App
   :no-members:
   :show-inheritance:

The main class for creating SOAR applications.

Key Methods
^^^^^^^^^^^

.. automethod:: soar_sdk.app.App.action
.. automethod:: soar_sdk.app.App.test_connectivity
.. automethod:: soar_sdk.app.App.on_poll
.. automethod:: soar_sdk.app.App.register_action
.. automethod:: soar_sdk.app.App.enable_webhooks
.. automethod:: soar_sdk.app.App.view_handler

ActionResult
~~~~~~~~~~~~

.. autoclass:: soar_sdk.action_results.ActionResult
   :members: set_status, add_data, get_status
   :show-inheritance:

APIs
----

Artifact API
~~~~~~~~~~~~

.. autoclass:: soar_sdk.apis.artifact.Artifact
   :members: create
   :show-inheritance:

Container API
~~~~~~~~~~~~~

.. autoclass:: soar_sdk.apis.container.Container
   :members: create, set_executing_asset
   :show-inheritance:

Vault API
~~~~~~~~~

.. autoclass:: soar_sdk.apis.vault.Vault
   :members: create_attachment, add_attachment, get_attachment, delete_attachment
   :show-inheritance:

Logging
----------

.. autoexception:: soar_sdk.logging.getLogger
   :show-inheritance:

.. autoexception:: soar_sdk.logging.info
   :show-inheritance:

.. autoexception:: soar_sdk.logging.debug
   :show-inheritance:

.. autoexception:: soar_sdk.logging.progress
   :show-inheritance:

.. autoexception:: soar_sdk.logging.warning
   :show-inheritance:

.. autoexception:: soar_sdk.logging.error
   :show-inheritance:

.. autoexception:: soar_sdk.logging.critical
   :show-inheritance:

Exceptions
----------

.. autoexception:: soar_sdk.exceptions.ActionFailure
   :show-inheritance:

.. autoexception:: soar_sdk.exceptions.SoarAPIError
   :show-inheritance:
