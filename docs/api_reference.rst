API Reference
=============

This section documents the public API of the Splunk SOAR SDK.

Core Functionality
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

Asset Configuration
~~~~~~~~~~~~

AssetField
^^^^^^^^^^

.. autofunction:: soar_sdk.asset.AssetField
   :noindex:

BaseAsset
^^^^^^^^^^

.. autoclass:: soar_sdk.asset.BaseAsset
   :members: to_json_schema
   :show-inheritance:
   :exclude-members: validate_no_reserved_fields


Action Parameters
~~~~~~~~~~~~

Action parameters are defined in Pydantic models, which extend the ``soar_sdk.params.Params`` class.
At their most basic, parameters can have a simple data type such as ``str`` or ``int``.

.. code-block:: python

   from soar_sdk.params import Params


   class CreateUserParams(Params):
      username: str
      first_name: str
      last_name: str
      email: str
      is_admin: bool
      uid: int


Adding extra metadata
^^^^^^^^^^^^^^^^^^^^^^

You can use the ``Param`` function to add extra information to a parameter type.
For example, let's give the ``uid`` field a Common Event Format (CEF) type and make it optional.

.. code-block:: python

   from soar_sdk.params import Params, Param


   class CreateUserParams(Params):
      username: str
      first_name: str
      last_name: str
      email: str
      is_admin: bool
      uid: int = Param(required=False, cef_types=["user id"])

For a full list of Param options, see the ``Params`` class and ``Param`` function below:

.. autoclass:: soar_sdk.params.Params

.. autofunction:: soar_sdk.params.Param

Action Outputs
~~~~~~~~~~~~

Basic Return Types
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Actions in the SOAR SDK can return values in several simple formats for basic success/failure reporting:

**Boolean Return (`bool`)**

The simplest return type. Actions can return just `True` for success or `False` for failure:

.. code-block:: python

   @app.action()
   def simple_action(params: Params, client: SOARClient, asset: Asset) -> bool:
       # Perform some operation
       if operation_successful:
           return True
       return False

**Tuple Return (`tuple[bool, str]`)**

For more descriptive results, actions can return a tuple with a boolean status and a message:

.. code-block:: python

   @app.action()
   def descriptive_action(params: Params, client: SOARClient, asset: Asset) -> tuple[bool, str]:
       try:
           # Perform operation
           return True, "Operation completed successfully"
       except Exception as e:
           return False, f"Operation failed: {str(e)}"

**ActionResult Classes**

For more control over action results, use these result classes:

.. autoclass:: soar_sdk.action_results.ActionResult
   :show-inheritance:

.. autoclass:: soar_sdk.action_results.SuccessActionResult
   :show-inheritance:

.. autoclass:: soar_sdk.action_results.ErrorActionResult
   :show-inheritance:

Customizable Output Classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To provide more detailed action output, you can use the ActionOutput class:

.. autoclass:: soar_sdk.action_results.OutputField
   :show-inheritance:

.. autoclass:: soar_sdk.action_results.ActionOutput
   :show-inheritance:
   :exclude-members: to_json_schema

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

Data Models
-----------

.. autoclass:: soar_sdk.models.artifact.Artifact
   :exclude-members: Config

.. autoclass:: soar_sdk.models.container.Container
   :exclude-members: Config

.. autoclass:: soar_sdk.models.vault_attachment.VaultAttachment
   :exclude-members: Config

.. autoclass:: soar_sdk.models.view.ViewContext
   :exclude-members: Config

.. autoclass:: soar_sdk.models.view.ResultSummary
   :exclude-members: Config

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

.. automodule:: soar_sdk.exceptions
   :members:
   :show-inheritance:
   :exclude-members: __init__, __cause__, __context__, __suppress_context__, __traceback__, __notes__, args, __str__, set_action_name
