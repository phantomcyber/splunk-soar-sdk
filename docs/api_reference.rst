.. _api_reference:

API Reference
=============

This section documents the public API of the Splunk SOAR SDK.

Jump to a Section:
------------------

- :ref:`api_ref_core_label`
- :ref:`api_ref_key_methods_label`
- :ref:`asset-configuration-label`
- :ref:`action-param-label`
- :ref:`action-output-label`
- :ref:`soar-client-label`
- :ref:`api_ref_apis_label`
- :ref:`api_ref_data_models_label`
- :ref:`api_ref_logging_label`
- :ref:`api_ref_exceptions_label`

.. _api_ref_core_label:

The App Class
-------------

.. autoclass:: soar_sdk.app.App
   :show-inheritance:
   :exclude-members: action, test_connectivity, on_poll, register_action, enable_webhooks, view_handler, make_request

.. _api_ref_key_methods_label:

Key App Methods
~~~~~~~~~~~~~~~

.. automethod:: soar_sdk.app.App.action
.. automethod:: soar_sdk.app.App.test_connectivity
.. automethod:: soar_sdk.app.App.on_poll
.. automethod:: soar_sdk.app.App.register_action
.. automethod:: soar_sdk.app.App.enable_webhooks
.. automethod:: soar_sdk.app.App.view_handler
.. automethod:: soar_sdk.app.App.make_request

.. _asset-configuration-label:

Asset Configuration
~~~~~~~~~~~~~~~~~~~

AssetField
^^^^^^^^^^

.. autofunction:: soar_sdk.asset.AssetField

.. note::
   The ``required`` keyword argument is deprecated and will be removed in the next
   major version. Prefer Optional type hints (``str | None``) to indicate optional
   asset fields.

BaseAsset
^^^^^^^^^

.. autoclass:: soar_sdk.asset.BaseAsset
   :members: to_json_schema
   :show-inheritance:
   :exclude-members: validate_no_reserved_fields

Validated Network Hosts
^^^^^^^^^^^^^^^^^^^^^^^

Use :data:`soar_sdk.networking.Host` for an asset field that accepts an IP address
or hostname without a URL scheme, port, or path. It normalizes IP addresses and
hostnames while retaining a plain ``str`` value. Surrounding whitespace, a trailing
DNS dot, and accidental trailing slashes are removed.

Use :func:`soar_sdk.networking.format_url_host` when inserting the value into a URL.
The function adds the brackets required around an IPv6 address in a URL authority.

.. code-block:: python

   from soar_sdk.asset import AssetField, BaseAsset
   from soar_sdk.networking import Host, format_url_host


   class Asset(BaseAsset):
      device: Host = AssetField(description="Device IP address or hostname")
      port: int = AssetField(default=443)


   def get_base_url(asset: Asset) -> str:
      return f"https://{format_url_host(asset.device)}:{asset.port}/"

.. autodata:: soar_sdk.networking.Host

.. autofunction:: soar_sdk.networking.format_url_host


.. _action-param-label:

Action Parameters
~~~~~~~~~~~~~~~~~

Action parameters are defined in Pydantic models, which extend the :class:`soar_sdk.params.Params` class.
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


Adding Extra Metadata
^^^^^^^^^^^^^^^^^^^^^

You can use the :func:`~soar_sdk.params.Param` function to add extra information to a parameter type.
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

.. note::
   The ``required`` keyword argument is deprecated and will be removed in the next
   major version. Prefer Optional type hints (``str | None``) to indicate optional
   action parameters.

Defining Parameters
^^^^^^^^^^^^^^^^^^^

.. autoclass:: soar_sdk.params.Params

.. autofunction:: soar_sdk.params.Param

Parameters For ``on poll``
^^^^^^^^^^^^^^^^^^^^^^^^^^
On poll functions require a specific parameter class called `OnPollParams`. YYou should use this class as-is, instead of overriding it.

.. autoclass:: soar_sdk.params.OnPollParams

Parameters for the Make Request Action
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Make Request action functions require a specific parameter class called :class:`~soar_sdk.params.MakeRequestParams`. You should use this class as-is, instead of overriding it.

.. autoclass:: soar_sdk.params.MakeRequestParams


.. _action-output-label:

Action Outputs
~~~~~~~~~~~~~~

Action outputs are defined in Pydantic models, which extend the :class:`~soar_sdk.action_results.ActionOutput` class.

Much like parameters, outputs can have simple data types such as ``str`` or ``int``, or be annotated with the :func:`~soar_sdk.action_results.OutputField` function to add extra metadata.

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

You can add summary data and a result message to your action, by calling :func:`soar_sdk.abstract.SOARClient.set_message` and :func:`soar_sdk.abstract.SOARClient.set_summary`. Summary objects are also subclasses of :class:`~soar_sdk.action_results.ActionOutput`, and you must register them in your action decorator:

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


Defining Action Outputs
^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: soar_sdk.action_results.ActionOutput

.. autofunction:: soar_sdk.action_results.OutputField

Make Request Action Output
^^^^^^^^^^^^^^^^^^^^^^^^^^
For ``make request`` functions, we have provided a convenience class called :class:`~soar_sdk.action_results.MakeRequestOutput`. This class extends the :class:`~soar_sdk.action_results.ActionOutput` class and adds a ``status_code`` and ``response_body`` field. You can use this class to return the response from the ``make request`` action.

.. autoclass:: soar_sdk.action_results.MakeRequestOutput

.. _soar-client-label:

SOARClient
~~~~~~~~~~~

The ``SOARClient`` class is an app's gateway to the Splunk SOAR platform APIs. It provides methods for creating and manipulating platform objects such as containers, artifacts, and vault items.

.. autoclass:: soar_sdk.abstract.SOARClient
   :show-inheritance:

.. _api_ref_apis_label:

APIs
----

Artifact API
~~~~~~~~~~~~

.. autoclass:: soar_sdk.apis.artifact.Artifact
   :members: create
   :show-inheritance:

Attachments API
~~~~~~~~~~~~~~~

Ingestion runtime bundles provide attachment operations through an
execution-time bridge, which the SDK exposes as ``soar.attachments``. The bridge
supplies task-scoped authentication and tenant identity and accepts calls only
during ``on_es_poll`` execution. It is not a dependency to install from PyPI.

Request targets for a batch of 1 through 20 files, using a UUID idempotency key.
Reuse the key with the same ordered file names when retrying that batch's target
lookup. Changing the file names with the same key causes a service conflict.
The returned targets contain stable attachment IDs, ordered multipart form fields,
expiration times, and maximum file sizes. Call
``soar.attachments.upload_file(local_path, target)`` for each downloaded file.
It streams a multipart POST with the original ordered form fields (including
repeated names), followed by the file part. It uses the target's file name,
expiry and size limit. Each successful response (HTTP 200, 201 or 204) returns an
``AttachmentUploadResult`` containing ``attachment_id``, ``file_name`` and
``size_bytes``. The ID is the existing target's identity; upload does not create
another attachment record or associate it with a finding.

For parallel uploads, call ``soar.attachments.upload_files([(path, target), ...])``.
It uses at most four concurrent uploads by default; ``max_workers=1`` makes
uploads sequential, and any positive integer can override the limit. The SDK
starts no more workers than there are files. Each file still uses its own S3
POST; upload targets are consumed, not requested again. No retry is attempted.
The method waits for all uploads and returns ``AttachmentUploadOutcome`` objects
in input order, preserving the file-to-attachment mapping even if completion
order differs. Each outcome contains ``attachment_id``, ``file_name`` and
``success``. Successful outcomes include ``size_bytes``; failures include a safe
``error_code``, ``message`` and, when available, ``status_code``.

Invalid pair shapes, repeated attachment IDs and invalid worker counts reject
the whole batch with ``ActionFailure`` before any upload. An empty batch returns
``[]``. Individual upload failures are reported in their outcomes and do not
stop other files. Reserve targets once for the batch through AR-2060 before
calling ``upload_files``; the existing 20-target reservation limit still applies.

Uploads use isolated HTTPS connections without SOAR authentication,
cookies, redirects or retries. HTTPS certificates are verified. The socket
timeout defaults to 30 seconds and can be overridden with a positive finite
``timeout`` value. It is not an overall batch deadline. Signed URLs, form values,
file contents and server response bodies are not logged or included in upload
results or exceptions. The caller owns the downloaded files and must delete them
in a ``finally`` block, whether polling succeeds or fails.

Upload URLs and form field values are credentials, stored as
:class:`~pydantic.SecretStr`. ``repr``, ``model_dump`` and ``model_dump_json``
mask them; call ``get_secret_value()`` only when building the upload request. Do
not log them or use upload URLs as finding download links. HTTP client errors
often include the request URL in their message, so do not log or re-raise upload
errors unmodified; report a message that omits the URL instead. Findings
reference the stable ``attachment_id`` values through associations, rather than
signed URLs.

Once uploads succeed and ES returns the finding IDs, queue their associations:

.. code-block:: python

   targets = soar.attachments.get_upload_targets(
       ["email.eml", "evidence.pdf", "second.eml"], batch_id
   )

   # Keep local_paths in the same order as the names requested above.
   successful_ids = {"first": [], "second": []}
   owners = ["first", "first", "second"]
   outcomes = soar.attachments.upload_files(
       list(zip(local_paths, targets, strict=True)), max_workers=4
   )
   for uploaded, owner in zip(outcomes, owners, strict=True):
       if not uploaded.success:
           # Record uploaded.attachment_id and uploaded.error_code; continue.
           continue
       successful_ids[owner].append(uploaded.attachment_id)

   # Create each finding using only its successfully uploaded attachments.
   # Link only successful uploads belonging to findings that ES created.
   # After ES returns first_finding_id and second_finding_id:
   # Include only the findings whose creation succeeded.
   created_findings = {"first": first_finding_id, "second": second_finding_id}
   associations = [
       {"subject_id": finding_id, "attachment_ids": successful_ids[owner]}
       for owner, finding_id in created_findings.items()
       if successful_ids[owner]
   ]
   if associations:
       message_id = soar.attachments.associate_subject_attachments(associations)

The association response confirms durable enqueueing. Timeline processes the
association asynchronously. Subject IDs are opaque ES finding IDs and need not
be UUIDs.

Error behavior:

- Invalid inputs (no file names, blank names or key, an empty association list,
  blank subject or attachment IDs, or unknown association keys) raise
  :class:`~soar_sdk.exceptions.ActionFailure` before the runtime is called.
- A missing, broken, or failing runtime bridge raises
  :class:`~soar_sdk.exceptions.AttachmentApiError`, a subclass of
  ``ActionFailure``. Runtime failures use fixed SDK messages, including when
  the bridge raises ``ActionFailure``. Upstream messages are not copied, and
  the original exception is not retained as ``__cause__`` or ``__context__``.
  Validation errors are not retained as ``__cause__`` or ``__context__`` either.
  Invalid raw upload targets are removed from SDK traceback frame locals
  before raising an error, so error reporters do not capture their credentials.
  This keeps pre-signed URLs and credentials out of SDK errors and tracebacks;
  callers do not need to handle runtime transport exceptions.
- Record creation also raises ``AttachmentApiError`` when the runtime returns
  invalid targets (including a non-HTTPS upload URL or no form fields) or
  targets that do not match the requested file names in
  order, including repeated names, or returns duplicate attachment IDs within
  the batch. Association raises it when the runtime does not return a nonblank
  queue message ID.
- Batch limits and idempotency-key UUID validity are enforced by the runtime
  service. These methods do not retry runtime failures. Target-creation
  idempotency does not extend to finding association: a queued association does
  not establish that a repeat association request will succeed.

Upload failures raise :class:`~soar_sdk.exceptions.AttachmentUploadError`, a
subclass of ``AttachmentApiError``. Inspect ``error_code``:

- ``validation``: invalid inputs or a file exceeding the target size limit.
- ``expired``: the target expired before upload started.
- ``file``: the local file could not be opened or inspected.
- ``authorization``: HTTP 401 or 403 (including expired credentials rejected by S3).
- ``rejected``: another HTTP 4xx response.
- ``unavailable``: network failure, interrupted file transfer, or HTTP 5xx.
- ``timeout``: a socket operation timed out.
- ``response``: an unexpected status, including a redirect.

The error carries ``attachment_id`` (absent for an invalid target) and
``status_code`` (absent without an HTTP response). It retains no original
exception chain. Catch errors per attachment: exclude failed uploads from finding
references and linking. A timeout may occur after S3 accepted the bytes; the SDK
does not automatically retry or reserve a new ID. Linking remains the separate
AR-2060 bundle → orchestrator → SQS → Timeline operation.

Upload support requires an SDK release containing AR-2060 and AR-2063, on Python
3.13 or 3.15. It consumes the AR-2060 multipart POST target contract; it does not
depend on an ES server version. ES finding compatibility is governed separately
by the finding creation API. This feature is unreleased in the 7.1.3 checkout.

.. autoclass:: soar_sdk.models.attachment_upload.AttachmentUploadOutcome

.. autoclass:: soar_sdk.models.attachment_upload.AttachmentUploadResult

These methods provide the attachment capability independently of automatic
polling. The ``@app.on_es_poll()`` decorator still uses its classic SOAR path.
Automatic runtime selection, the ES finding/reference schema, and checkpoint
and retry behavior across finding creation and queued association require the
corresponding integration contracts before that path can be connected.

.. autoclass:: soar_sdk.apis.attachments.Attachments
   :members: get_upload_targets, upload_file, upload_files, associate_subject_attachments

.. autoclass:: soar_sdk.models.attachment_upload.AttachmentUploadTarget

.. autoclass:: soar_sdk.models.attachment_upload.AttachmentUploadFormField

.. autoclass:: soar_sdk.models.attachment_upload.SubjectAttachmentAssociation

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

Finding Models
~~~~~~~~~~~~~~

Use these models when creating findings via :meth:`~soar_sdk.abstract.SOARClient.create_finding`
or :meth:`~soar_sdk.abstract.SOARClient.create_findings_bulk`. Build a :class:`~soar_sdk.models.finding.Finding`,
then pass its :meth:`~soar_sdk.models.finding.Finding.to_dict` output to the method.

.. autoclass:: soar_sdk.models.finding.Finding
   :members: to_dict
   :exclude-members: Config

.. autoclass:: soar_sdk.models.finding.FindingEmail
   :exclude-members: Config

.. autoclass:: soar_sdk.models.finding.FindingEmailReporter
   :exclude-members: Config

.. autoclass:: soar_sdk.models.finding.FindingEmailAttachment
   :exclude-members: Config

.. autoclass:: soar_sdk.models.finding.FindingAttachment
   :exclude-members: Config

.. autoclass:: soar_sdk.models.finding.DrilldownSearch
   :exclude-members: Config

.. autoclass:: soar_sdk.models.finding.DrilldownDashboard
   :exclude-members: Config

.. autoclass:: soar_sdk.models.finding.DrilldownDashboardToken
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
