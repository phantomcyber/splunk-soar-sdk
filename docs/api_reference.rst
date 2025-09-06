.. _api_reference:

API Reference
=============

This section documents the public API of the Splunk SOAR SDK.

Jump to a section:
------------------

- :ref:`api_ref_core_label`
- :ref:`api_ref_key_methods_label`
- :ref:`asset-configuration-label`
- :ref:`action-param-label`
- :ref:`action-output-label`
- :ref:`api_ref_apis_label`
- :ref:`api_ref_data_models_label`
- :ref:`api_ref_logging_label`
- :ref:`api_ref_exceptions_label`

.. _api_ref_core_label:

The App Class
-------------

.. autoclass:: soar_sdk.app.App
   :show-inheritance:
   :exclude-members: action, test_connectivity, on_poll, register_action, enable_webhooks, view_handler, generic_action

.. _api_ref_key_methods_label:

Key App Methods
~~~~~~~~~~~~~~~

.. automethod:: soar_sdk.app.App.action
.. automethod:: soar_sdk.app.App.test_connectivity
.. automethod:: soar_sdk.app.App.on_poll
.. automethod:: soar_sdk.app.App.register_action
.. automethod:: soar_sdk.app.App.enable_webhooks
.. automethod:: soar_sdk.app.App.view_handler
.. automethod:: soar_sdk.app.App.generic_action

.. _asset-configuration-label:

Asset Configuration
~~~~~~~~~~~~~~~~~~~

AssetField
^^^^^^^^^^

.. autofunction:: soar_sdk.asset.AssetField

BaseAsset
^^^^^^^^^

.. autoclass:: soar_sdk.asset.BaseAsset
   :members: to_json_schema
   :show-inheritance:
   :exclude-members: validate_no_reserved_fields


.. _action-param-label:

Action Parameters
~~~~~~~~~~~~~~~~~

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
^^^^^^^^^^^^^^^^^^^^^

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

Parameters for on poll
^^^^^^^^^^^^^^^^^^^^^^
On poll functions require a specific parameter class called `OnPollParams`. YYou should use this class as-is, instead of overriding it.

.. autoclass:: soar_sdk.params.OnPollParams

Parameters for generic action
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Generic action functions require a specific parameter class called `GenericActionParams`. You should use this class as-is, instead of overriding it.

.. autoclass:: soar_sdk.params.GenericActionParams


.. _action-output-label:

Action Outputs
~~~~~~~~~~~~~~

Action outputs are defined in Pydantic models, which extend the ``soar_sdk.action_results.ActionOutput`` class.

Much like parameters, outputs can have simple data types such as ``str`` or ``int``, or be annotated with the ``OutputField`` function to add extra metadata.

.. code-block:: python

   from soar_sdk.action_results import ActionOutput, OutputField

   class CreateUserOutput(ActionOutput):
      uid: int = OutputField(cef_types=["user id"])
      create_date: str

Output models can be nested, allowing you to create complex data structures:

.. code-block:: python

   from soar_sdk.action_results import ActionOutput, OutputField

   class UserDetails(ActionOutput):
      uid: int = OutputField(cef_types=["user id"])
      username: str
      email: str

   class CreateUserOutput(ActionOutput):
      user_details: UserDetails
      create_date: str

   class ListUsersOutput(ActionOutput):
      users: list[UserDetails]

You can add summary data and a result message to your action, by calling `client.set_message` and `client.set_summary`. Summary objects are also subclasses of `ActionOutput`, and you must register them in your action decorator:

.. code-block:: python

   from soar_sdk.action_results import ActionOutput, OutputField
   from soar_sdk.abstract import SOARClient

   class UserSummary(ActionOutput):
      total_users: int
      active_users: int
      inactive_users: int

   @app.action(summary_type=UserSummary)
   def list_users(params: ListUsersParams, soar: SOARClient[UserSummary]) -> ListUsersOutput:
       ...
       soar.set_summary(UserSummary(total_users=100, active_users=80, inactive_users=20))
       soar.set_message("Found 100 users")
       return ListUsersOutput(users=users)


For more details, see the ``ActionOutput`` class and the ``OutputField`` function below:

.. autoclass:: soar_sdk.action_results.ActionOutput

.. autofunction:: soar_sdk.action_results.OutputField

Generic Action Output
^^^^^^^^^^^^^^^^^^^^^
For generic action functions we have provided a convenience class called `GenericActionOutput`. This class extends the `ActionOutput` class and adds a status_code and response_body field. You can use this class to return the response from the generic action.

.. autoclass:: soar_sdk.action_results.GenericActionOutput

.. _api_ref_apis_label:

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

.. _api_ref_data_models_label:

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

.. _api_ref_logging_label:

Logging
-------

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

.. _api_ref_exceptions_label:

Exceptions
----------

.. automodule:: soar_sdk.exceptions
   :members:
   :show-inheritance:
   :exclude-members: __init__, __cause__, __context__, __suppress_context__, __traceback__, __notes__, args, __str__, set_action_name
