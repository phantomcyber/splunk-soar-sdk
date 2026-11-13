Direct ES Finding Creation
==========================

Connectors use the existing ``soar.create_finding(payload)`` and
``soar.create_findings_bulk(payloads)`` methods. The SDK selects the transport
through the execution runtime adapter: classic SOAR uses its existing proxy;
the ingestion bundle supplies the execution's paired ES context for direct public
API calls. The polling decorator selects this path when that context is present.
Connectors do not choose endpoints or pass credentials.

The source of truth is the `ES public OpenAPI specification
<https://cd.splunkdev.com/EnterpriseSecurity/app-ess/-/blob/0eb5d6679945524c0e101fc5d67482773f46ae51/packages/missioncontrol/packages/app/public_openapi_specs/mcopenapi_public.yaml>`_,
particularly ``POST /public/v2/findings``, ``CreateManualFindingRequest``,
``CreateManualFindingResponse``, ``DrilldownSearch`` and ``DrilldownDashboard``.
The test fixture records the source revision and copies the referenced schemas.
Update the SDK models and fixture together when that contract changes.

Inputs and Return Values
------------------------

.. code-block:: python

   from soar_sdk.models.es_finding import CreateFindingRequest

   request = CreateFindingRequest(
       rule_title="Reported phishing email",
       security_domain="threat",
       finding_source="Mail connector",
   )
   response = soar.create_finding(request.to_dict())
   finding_id = response["finding_id"]

The existing return type is preserved: ``create_finding`` returns a dictionary,
not an ID string. Direct ES responses include ``finding_id`` and ``_time``, plus
other documented ES properties when supplied. Unknown response properties are
ignored. Invalid or credential-echoing success responses raise ``FindingAPIError``.

For existing ``Finding.to_dict()`` payloads, in direct mode only,
the SDK wraps a single reporter ``to``, ``cc`` or ``bcc`` address in a list and
converts an ``additional_fields`` mapping into ES name/value entries. String
values are required for those entries. These adaptations do not mutate the
finding or the caller's dictionary. The OpenAPI models retain their strict
wire types, and classic SOAR receives the original payload unchanged. Other
fields must match the public ES contract; classic dashboard objects are not
converted because their wire mapping has not been confirmed.

``create_findings_bulk([request.to_dict(), ...])`` preserves its existing
25-finding limit and dictionary envelope: ``status``, ``created``, ``failed``,
``findings`` (successful IDs), ``container_ids`` and ``errors``. Classic SOAR's
proxy response is returned unchanged. In direct ES mode, the SDK issues one
single-create POST per input and additionally returns ordered ``results``:

.. code-block:: python

   batch = soar.create_findings_bulk([request.to_dict(), another_request.to_dict()])
   for result in batch["results"]:
       if result["success"]:
           finding_id = result["finding_id"]
       else:
           report_failure(result["index"], result["error_code"], result["message"])

Each direct result contains its zero-based ``index``, ``success`` and either
``finding_id`` or safe ``error_code``/``message`` and an HTTP ``status_code`` when
available. ``errors`` also contains the failed input indexes and safe messages.
The batch status is ``success``, ``partial`` or ``error``. Invalid items and HTTP
failures do not prevent later findings from being attempted. Empty input returns
an empty successful envelope. More than 25 inputs raises the existing ``ValueError``;
callers split larger batches before calling. The operation is not atomic.

ES OpenAPI also defines ``POST /public/v2/findings/bulk_create`` with a server
limit of 500 findings. That limit is distinct from the SDK's existing limit of
25. Its response supplies indexes for errors, but only a list of IDs for
successful findings. The inspected ES implementation partitions suppressed and
ordinary findings before building that ID list, so it can change the input
order. Correct per-input IDs (and attachment associations) require an indexed
success response or a server guarantee that the original order is preserved.
Do not infer finding-to-attachment mappings from an unordered ID list.

Direct mode creates no SOAR containers and returns ``container_ids: []``.
Supplying ``container_ids`` in direct mode raises ``FindingConfigurationError``;
classic mode retains its existing container-linking behavior.

Runtime Integration
-------------------

The protected ``SOARClient._get_es_finding_context()`` hook lazily calls the
ingestion bundle's ``es_poll_api.get_es_context()`` for the current execution's
``(base_url, token)``. It is called per single operation or once per bulk
operation; credentials are never cached on the SDK client. The token may be a
string or ``pydantic.SecretStr``. URL/token are internal transport inputs, not
new connector API arguments. The adapter must obtain them from execution-scoped
action data, never from asset configuration or hard-coded values.

Classic SOAR has no bridge and retains its proxy behavior. The companion
``soar-services`` change packages the bridge only in ingestion bundles. It exposes
context only for ``EXECUTOR_TASK_KIND=ingestion`` and ``ACTION_NAME=on_es_poll``.
The orchestrator supplies ``ES_BASE_URL`` from the credential's ``endpoint`` in
the same lookup that supplies ``ES_INGESTION_TOKEN``. The bridge reads the token
through ``RuntimeCredentials.current()``; it performs no credential retrieval or
refresh. Missing context or a broken bridge becomes a safe
``FindingConfigurationError``, with no silent proxy fallback.

During direct polling, ``OnESPollParams.base_url`` and ``access_token`` expose
the runtime context as read-only properties; ``access_token`` is a ``SecretStr``.
Their backing values are private attributes, excluded from manifests, model
dumps, JSON schemas and representations. They are cleared when polling exits.
They are not accepted as ordinary action parameters. Classic polling sees
``None`` for both. Token retrieval and refresh belong to automationOrchestrator.

``base_url`` accepts a stack origin (``https://stack:8089``) or the full OpenAPI
server URL (``https://stack:8089/servicesNS/nobody/missioncontrol``). For an origin,
the SDK adds the namespace prefix. A trailing slash is accepted. It then appends
``/public/v2/findings``; it does not use the RFC's
``/rest/findings`` path. URL credentials, query strings and fragments are rejected.
Use HTTPS for the paired stack; HTTP is supported for local simulation.

The runtime must supply an actual absolute endpoint URL. The inspected
ES publisher can publish a short stack identifier such as ``sh-i-abc123.stack``;
that value is not sufficient for routing. The SDK rejects it rather than
guessing a scheme, domain suffix or port. Confirm a full endpoint is published
for the ingestion credential before enabling this path. No separate tenant URL
mapping or connector-owned endpoint is introduced.

The private HTTP transport uses a separate client with TLS verification, no
redirects and a 30-second timeout per request. SOAR cookies/authentication are
never sent to ES. Neither single nor bulk direct operations retry POSTs. The
classic single and bulk timeout behavior is preserved.

Direct Polling and Attachments
------------------------------

``@app.on_es_poll()`` keeps the existing ``yield Finding`` interface. With runtime
ES context it uses direct creation without SOAR REST, containers or vault calls.
Asset defaults come from the supplied asset configuration's ``ingest`` mapping.
``App.handle()`` captures this mapping before classic ``IngestConfig`` validation;
ES settings do not require ``container_label`` or become connector asset fields.
Single and async generators are supported. Batch creation uses at most 25 findings
and normally at most 20 local attachments, the upload-target service limit;
``container_count`` limits attempted findings, including failures.

Each action-result data row contains the input index and the created finding ID
or safe failure details. The summary includes ``created``, ``failed``,
``polling_failed``, ``attachments_uploaded``, ``attachments_failed``, ``links_queued``,
``links_failed`` and ``status``. Mixed outcomes report ``partial`` and processing
continues; all-failed or handler/state failures report an unsuccessful action.
An empty poll succeeds. Generators are closed on exit, including a count limit.

After normal generator completion, attempted-work checkpoint changes are committed
even when individual findings failed. Failed POSTs and timeouts are reported, not
automatically replayed: replaying successes can create duplicates. Handler or state
failures make the action unsuccessful; buffered state is rolled back where possible.
Previously created findings remain created and their IDs remain in the result.
Reconcile those IDs before retrying such a run. Classic polling is unchanged.

For each yielded ``Finding``, local ``Finding.attachments`` are handled in order:

#. The decorator writes their bytes to SDK-owned temporary files and requests
   targets through ``soar.attachments.get_upload_targets`` (AR-2060). Each
   attachment batch makes one bulk reservation with a new UUID idempotency key.
   A finding with more than 20 files uses consecutive reservations of at most 20.
   Returned IDs must be UUIDs and must not be reused anywhere in the run.
#. ``soar.attachments.upload_files`` (AR-2063) uploads the files with at most four
   workers. Temporary files are removed on success and failure. Input names are
   metadata only; they are never used as local paths.
#. Only successful uploads populate ``email.attachments`` entries with
   ``filename``, ``filesize`` and ``url``. The last successful local attachment
   marked ``is_raw_email=True`` also supplies ``email.raw_email_link``, matching
   classic polling's selection rule. Local attachments replace the corresponding
   existing attachment references in a copy of the finding payload.
#. Findings are created with ordered individual POSTs. Their returned IDs are
   paired with their own successful attachment IDs in one bulk
   ``soar.attachments.associate_subject_attachments`` call per finding batch.
   Failed findings are never linked. Findings without files make no attachment
   calls. Neither findings nor attachment operations are automatically retried.

The reference URL is provisional, pending the final ES attachment contract. Its
base route comes from the private execution bundle's
``es_poll_api.get_attachment_reference_base_url()``; the SDK appends
``?attachment_id=<UUID>``. It must use the same origin as the paired ES context.
No token or presigned URL is embedded. ES readers must interpret the reference
as an identity and retrieve content through the automation provider. It is not
a general-purpose download URL. The public OpenAPI schema accepts a URI but
does not yet define these reference semantics.

Reservation, reference-route and local-file failures are reported per attachment;
findings continue without failed files. Each finding result's ``attachments``
list preserves local attachment order. Upload outcomes include their stable ID,
success or safe failure details; failures before reservation have no ID.
``attachment_links`` records ``queued`` or ``failed`` with the affected IDs.
An attachment or link failure makes an otherwise successful poll ``partial``.

An association ACK confirms queueing through bundle → orchestrator → SQS. It
does not confirm that Timeline has saved the mapping. ES/SAA may try reading
before that save and receive a missing-file response. This change provides no
readiness barrier or SAA retry policy; verify that race in the target environment
before enabling automatic threat analysis. Classic polling is unchanged.

Request Model Fields
--------------------

Import the following models from ``soar_sdk.models.es_finding``. ``rule_title``
and ``security_domain`` are required strings. All remaining request fields are
optional. ``None`` means omission; JSON null is not emitted. Omitted booleans
remain omitted, while explicit ``False`` is sent. ES owns defaults and
configuration-dependent rules such as requiring ``automation_rule`` when
``launch_automation`` is true, and URI/email format validation. Unknown request
fields and invalid types are
rejected instead of silently discarded.

.. list-table:: CreateFindingRequest
   :header-rows: 1
   :widths: 50 50

   * - Fields
     - Type and meaning
   * - ``rule_title``, ``security_domain``
     - Required strings: finding title and security domain.
   * - ``rule_description``
     - String: finding description.
   * - ``risk_object``, ``risk_object_type``
     - Strings: object and its type.
   * - ``risk_score``, ``risk_event_count``
     - Numbers; fractional values are supported by the schema.
   * - ``status``, ``urgency``, ``owner``, ``disposition``
     - Strings: ES labels or identifiers, as applicable.
   * - ``drilldown_searches``
     - List of ``DrilldownSearch`` objects.
   * - ``drilldown_dashboards``
     - List of ``DrilldownDashboard`` objects.
   * - ``annotations``
     - Mapping of strings to lists of strings, e.g. MITRE ATT&CK IDs.
   * - ``all_risk_objects``, ``source``, ``exclude_map_fields``
     - Lists of strings. The wire field is ``source``, not ``sources``.
   * - ``queue_id``, ``finding_source``, ``investigation_type``
     - Strings: queue, origin and investigation type.
   * - ``email``
     - ``PhishingEmail`` object described below.
   * - ``run_threat_analysis``, ``launch_automation``
     - Booleans controlling ES analysis and automation behavior.
   * - ``automation_rule``
     - String: automation rule/playbook name.
   * - ``additional_fields``
     - List of ``AdditionalField`` objects with optional string ``name`` and
       ``value``. Allowed event field names are validated by ES.

``DrilldownSearch`` requires string ``name``, ``search``, ``earliest`` and
``latest``. ``DrilldownDashboard`` requires string ``name`` and ``dashboard``;
optional ``tokens`` is a list of strings. These are the ES wire models, rather
than the classic SOAR dashboard model's ``app``, ``dashboard_id`` and name/value
token objects.

``PhishingEmail`` has optional ``headers`` (free-form object), ``body`` (string),
``urls`` (list of strings), ``attachments`` (list of ``EmailAttachment``),
``raw_email_link`` (URI string) and ``reporter`` (``EmailReporter``).
``EmailAttachment`` requires ``filename`` (string); optional ``filesize`` is an
integer from 0 through 2147483647 and ``url`` is a URI string. These are finding
metadata, not file bytes or presigned upload targets.

``EmailReporter`` requires ``from_`` in Python (``from`` on the wire). Its optional
``to``, ``cc`` and ``bcc`` are lists of strings. ``subject``, ``message_id``, ``id``,
``body`` and ``date`` are optional strings. The SDK does not truncate content;
server-side processing follows the ES contract.

Response Fields
---------------

``CreateFindingResponse`` requires ``finding_id`` and ``_time`` (both strings).
The Python attribute for ``_time`` is ``created_time``; serialize with
``model_dump(by_alias=True, exclude_none=True)`` to retain ES names.

Optional string fields are ``risk_object``, ``risk_score``, ``creator``,
``status``, ``urgency``, ``disposition``, ``owner_realname``, ``info_max_time``,
``queue_id``, ``finding_source``, ``investigation_type`` and ``automation_rule``.
``risk_object_type`` is ``system``, ``user`` or ``other``. Response ``risk_score``
is a string even though the request uses a number. ``drilldown_searches`` and
``drilldown_dashboards`` are lists of free-form objects; ``email`` is a free-form
object. ``run_threat_analysis`` and ``launch_automation`` are optional booleans.

Explicit Attachment API Calls
-----------------------------

The decorator handles this sequence for yielded ``Finding.attachments``.
Callers managing files explicitly can use the same SDK APIs without yielding
those files again; they own the batch, references, outcomes and cleanup:

1. Collect findings and download their attachments to temporary files.
2. Use one AR-2060 ``soar.attachments.get_upload_targets`` call per connector
   batch, with exactly the total number of attachment filenames in that batch.
   Assign each file exactly one returned ID; never reuse an ID. The
   reservation service accepts at most 20 files per request, so connector batch
   sizing must respect that attachment limit or the limit must be agreed with
   AR-2060. Do not request targets separately for each finding.
3. Upload bytes using AR-2063. Track success for each attachment ID. Presigned
   URLs and multipart field values are credentials, not permanent finding links.
4. Populate the ES attachment-reference fields with successful
   uploads, then call ``soar.create_findings_bulk`` (or ``soar.create_finding`` for one finding).
5. For successfully created findings only, pass the returned IDs unchanged to
   AR-2060's association API:

   .. code-block:: python

      batch = soar.create_findings_bulk([request.to_dict() for request in requests])
      results = batch["results"]
      associations = [
          {
              "subject_id": result["finding_id"],
              "attachment_ids": uploaded_ids_by_index[result["index"]],
          }
          for result in results
          if result["success"] and uploaded_ids_by_index.get(result["index"])
      ]
      if associations:
          message_id = soar.attachments.associate_subject_attachments(associations)

6. Report counts and per-finding/per-attachment failures, then delete temporary
   files in a ``finally`` block, whether the run succeeds or fails. Association
   returns a durable queue message ID; bundle → orchestrator → SQS → Timeline
   processing completes the link asynchronously. Enqueueing does not confirm
   completed linking.

When there are no attachments, skip upload target creation, uploads and linking.
If upload URL reservation fails, mark those attachments failed and create findings
without attachment references. The direct polling decorator continues and reports
``partial``. An individual failed upload must be excluded from both
finding references and associations; other files/findings continue.

ES requires ``email.raw_email_link`` when ``run_threat_analysis=True``. If the
raw email upload fails, that requested analysis may cause ES to reject the
finding. The SDK preserves analysis flags and reports the creation failure.
Callers may explicitly disable analysis to create a finding without raw email.

Finding errors are recorded per input; failed findings must never be linked.
If association fails, report the affected finding-ID/attachment-ID pairs and keep
the already-created findings. Do not recreate findings to retry linking. Neither
connectors nor the SDK retry ambiguous create POSTs automatically.

Connector code must use SDK APIs for reservations (AR-2060), byte uploads
(AR-2063), creation (AR-2061), and associations (AR-2060), without direct gRPC,
S3, ES REST calls or hard-coded endpoints. ES tokens, presigned URLs and file
contents must be excluded from logs, errors and run results across all stages.
Connector migrations and durable association verification belong to the shared
integration flow. The direct polling decorator composes these SDK APIs without
changing classic SOAR container and vault behavior.

.. important::

   The inspected OpenAPI does not define an attachment-ID property. It declares
   ``email.raw_email_link`` and attachment URLs as URIs. The runtime-supplied
   reference format is temporary and requires the matching ES reader update.
   AR-2060 association accepts stable IDs separately. Successful schema
   validation alone does not prove the reference is readable.

   Association is asynchronous. An ES consumer can attempt a download before
   Timeline has saved the finding-to-attachment link. The inspected SAA code
   treats download failures as terminal. The integration must handle that race
   before enabling immediate threat analysis or automation on new findings.

Errors and Retries
------------------

All finding exceptions inherit ``FindingAPIError`` and SDK ``ActionFailure``.

.. list-table:: Error mapping
   :header-rows: 1

   * - Condition
     - Exception / result error_code
   * - Invalid local payload or ES 4xx other than 401/403/429
     - ``FindingValidationError`` / ``validation``
   * - Invalid URL, token or timeout
     - ``FindingConfigurationError`` / ``configuration``
   * - Expired/unauthorized token (401) or forbidden operation (403)
     - ``FindingAuthorizationError`` / ``authorization``
   * - ES rate limit (429)
     - ``FindingRateLimitError`` / ``rate_limit``
   * - ES 5xx or connection/transport failure
     - ``FindingUnavailableError`` / ``unavailable``
   * - HTTP timeout
     - ``FindingTimeoutError`` / ``timeout``
   * - Unexpected status, malformed success, missing ID, credential echo
     - ``FindingAPIError`` / ``response``

Errors retain the HTTP status when available, but not ES response bodies or
upstream transport exceptions. Tokens are excluded from errors and results.
Payload validation failures occur before any HTTP call. The SDK performs no
automatic retries and does not refresh tokens. After timeout or lost response,
the finding may already exist: retrying a POST can create duplicates. Attachment
reservation's idempotency key does not make finding creation idempotent.

Compatibility and Verification
------------------------------

This API is introduced after SDK 7.1.3; use a released SDK containing this
feature. Release automation assigns the version. The models and schema tests
target ES OpenAPI version 8.8.0 at the revision linked above. Compatibility with
ES 8.2 or other releases is not implied: verify their public findings contracts
before declaring support. Python 3.13 and 3.15 follow the SDK's support policy.

Local schema tests check serialized requests against the copied ES schema;
HTTP tests check IDs, mixed batch outcomes, errors and secret handling. Polling
tests compose AR-2060/AR-2063 with creation, per-file outcomes and queued links.
Runtime action-data delivery and actual ES/Timeline
behavior must be verified on ``feature/phishing-sdk-changes`` after
the related changes merge. The classic models and proxy API remain available;
the direct methods adapt the supported legacy payload shapes internally.

.. automethod:: soar_sdk.abstract.SOARClient.create_finding
   :no-index:

.. automethod:: soar_sdk.abstract.SOARClient.create_findings_bulk
   :no-index:

.. autoclass:: soar_sdk.models.es_finding.CreateFindingRequest
   :members: to_dict

.. autoclass:: soar_sdk.models.es_finding.CreateFindingResponse

.. autoclass:: soar_sdk.models.es_finding.FindingCreateResult
   :members: success
