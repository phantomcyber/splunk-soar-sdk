Changelog
=========

The Splunk SOAR SDK follows a strict semantic versioning and continuous
delivery model. As such, that means every individual pull request results in a
release, typically with one semantic change.

Increments to the major version number imply a breaking change, to the minor
version imply a new feature, and to the patch version imply a non-breaking
bugfix.

.. dropdown:: SDK 5
   :open:

   .. rubric:: 5.0.1 (2026-09-18)

   * Docs: Document the SDK release history and CI-managed changelog workflow.

   .. rubric:: 5.0.0 (2026-09-15)

   **Breaking changes:**

   * Fix: ``soarapps install`` now verifies TLS certificates by default.
     Deployments using self-signed or otherwise untrusted certificates must
     install a trusted certificate or pass ``--insecure`` explicitly.
   * Fix: SDK HTTP clients now honor the platform TLS verification setting when
     creating and refreshing connections. Deployments that relied on disabled
     certificate verification must configure the platform and certificates
     accordingly.

.. dropdown:: SDK 4

   .. rubric:: 4.4.2 (2026-09-15)

   * Fix: Set Splunk SOAR 8.9.0 as the minimum version for apps that use Python script
     asset fields.

   .. rubric:: 4.4.1 (2026-09-09)

   * Fix: Refresh project dependencies.

   .. rubric:: 4.4.0 (2026-09-09)

   * Feature: Add support for Python script asset fields in asset models and manifests.

   .. rubric:: 4.3.0 (2026-09-09)

   * Feature: Add a validated host type for networking fields.
   * Docs: Update the repository branding and documentation assets.

   .. rubric:: 4.2.1 (2026-09-09)

   * Fix: Allow ``pythonwhois-alt`` to build from source when a compatible wheel is
     unavailable.

   .. rubric:: 4.2.0 (2026-09-08)

   * Feature: Add provenance metadata to generated SDK manifests.

   .. rubric:: 4.1.2 (2026-08-21)

   * Fix: Asset-state force reload behavior on modern Automation Broker versions.

   .. rubric:: 4.1.1 (2026-08-21)

   * Fix: Asset-state handling when encryption helpers are unavailable or perform
     no operation.
   * Fix: Restrict asset-state encryption changes to remote procedure call (RPC) brokers.
   * Docs: Clarify that encryption at rest is provided by Splunk SOAR.

   .. rubric:: 4.1.0 (2026-08-21)

   * Feature: Add the ``--lean`` option to ``soarapps init`` for smaller app scaffolds.

   .. rubric:: 4.0.0 (2026-08-15)

   **Breaking changes:**

   * Fix: Actions that omit ``read_only`` now default to non-read-only and are not
     eligible for Safe Mode. Apps that rely on Safe Mode must set
     ``read_only=True`` for every action that only reads data; actions that modify
     external systems must remain non-read-only.

.. dropdown:: SDK 3

   .. rubric:: 3.29.0 (2026-08-11)

   * Feature: Add ``phantom.cef`` and ``phantom.utils`` compatibility shims for legacy
     apps.

   .. rubric:: 3.28.1 (2026-08-06)

   * Fix: Preserve artifacts when polling retries a duplicate container.

   .. rubric:: 3.28.0 (2026-08-05)

   * Feature: Add support for external credential management.

   .. rubric:: 3.27.2 (2026-08-03)

   * Fix: Improve polling reliability by saving checkpoints after durable writes,
     failing when container saves fail, and preserving duplicate-container
     behavior.
   * Fix: Limit MIME-part traversal during email processing.

   .. rubric:: 3.27.1 (2026-08-03)

   * Fix: Validate IPv6 indicators extracted from email data.
   * Fix: Avoid selecting a malformed ``Authlib`` release during dependency
     resolution.

   .. rubric:: 3.27.0 (2026-08-03)

   * Feature: Add complete action-lock metadata, including a lock data path and timeout.
   * Feature: Deprecate ``enable_concurrency_lock``. Use ``lock=ActionLock(...)`` when an
     action requires exclusive locking.

   .. rubric:: 3.26.5 (2026-08-03)

   * Fix: Update dependencies and test tooling.

   .. rubric:: 3.26.4 (2026-07-29)

   * Fix: Update dependencies and pre-commit automation.

   .. rubric:: 3.26.3 (2026-07-22)

   * Fix: Improve email processing failure handling, including recursive parsing,
     inline body aggregation, and artifact saves.

   .. rubric:: 3.26.2 (2026-07-20)

   * Fix: Constrain ``Rich`` to versions below 15 for compatibility.

   .. rubric:: 3.26.1 (2026-07-17)

   * Fix: Expand email URL extraction.
   * Fix: Validate OAuth callback state.

   .. rubric:: 3.26.0 (2026-07-13)

   * Feature: Improve ``on_es_poll`` performance by parallelizing container and attachment
     writes.

   .. rubric:: 3.25.4 (2026-07-07)

   * Fix: Update ``idna`` to address a known security vulnerability.

   .. rubric:: 3.25.3 (2026-07-07)

   * Fix: Refresh dependency locks.

   .. rubric:: 3.25.2 (2026-07-02)

   * Fix: Correct SDK documentation links.

   .. rubric:: 3.25.1 (2026-06-22)

   * Fix: SDK app behavior on modern Automation Broker versions.

   .. rubric:: 3.25.0 (2026-06-15)

   * Feature: Add state-encryption flags and corresponding options to ``soarapps init``.

   .. rubric:: 3.24.0 (2026-06-11)

   * Feature: Add a guided initialization wizard to ``soarapps init``.
   * Feature: Add non-interactive initialization.
   * Fix: Default initialization output to the app directory.
   * Feature: Generate a private pre-commit configuration for new apps.

   .. rubric:: 3.23.0 (2026-06-11)

   * Feature: Support package-install authentication with ``PH_AUTH_TOKEN`` or
     ``PHANTOM_USERNAME`` and ``PHANTOM_PASSWORD``.
   * Feature: Allow the Splunk SOAR instance to be set with ``SOAR_INSTANCE``.

   .. rubric:: 3.22.3 (2026-06-11)

   * Fix: Improve compatibility with tuple-shaped ``vault_add`` responses.

   .. rubric:: 3.22.2 (2026-06-09)

   * Fix: ``on_poll`` automation scheduling so the final artifact in each
     container respects an explicit ``run_automation`` value.

   .. rubric:: 3.22.1 (2026-06-05)

   * Fix: Decryption for sensitive asset fields that use aliases.

   .. rubric:: 3.22.0 (2026-05-08)

   * Feature: Add optional ``additional_fields`` to Splunk Enterprise Security (ES)
     findings.
   * Docs: Document Finding models and their relationship to ``create_finding``.

   .. rubric:: 3.21.0 (2026-05-06)

   * Feature: Allow ``dec_key`` to be omitted when the platform does not provide one.

   .. rubric:: 3.20.1 (2026-04-27)

   * Fix: Include ``LICENSE`` and ``NOTICE`` files in built app packages.

   .. rubric:: 3.20.0 (2026-04-24)

   * Feature: Add ``soarapps manifests create-notice`` to generate a ``NOTICE`` file for
     app dependencies.

   .. rubric:: 3.19.2 (2026-04-13)

   * Fix: Allow list-returning actions to produce separate action results.
   * Fix: Add ``flatten_results`` to retain the existing single-result behavior when
     needed.

   .. rubric:: 3.19.1 (2026-04-06)

   * Fix: The ``__all__`` syntax generated for new app packages.

   .. rubric:: 3.19.0 (2026-04-06)

   * Feature: Include ``README.md`` and release notes in built app packages.
   * Feature: Add the optional ``--uv-index`` argument to ``soarapps init`` and
     ``soarapps convert``.

   .. rubric:: 3.18.1 (2026-03-30)

   * Fix: Limit ES poll batches to 25 findings.

   .. rubric:: 3.18.0 (2026-03-23)

   * Feature: Clean up containers left behind after a failed ES poll batch.
   * Feature: Add the ``remove_when_soar_newer_than(7.0.0)`` option to ``ph_ipc``.

   .. rubric:: 3.17.1 (2026-03-17)

   * Fix: Improve source builds by including ``red-black-tree-mod`` and normalizing
     dependency names.

   .. rubric:: 3.17.0 (2026-03-16)

   * Feature: Add parsing support for Microsoft Outlook MSG email files.
   * Feature: Organize email helpers under ``email_data`` while keeping compatible aliases
     for the previous ``rfc5322`` names.

   .. rubric:: 3.16.0 (2026-03-13)

   * Feature: Add reporter details and verification information to ES findings.
   * Fix: Remove the unused email dependency from the core SDK dependency set.

   .. rubric:: 3.15.1 (2026-03-09)

   * Fix: Finding construction for non-Automation Broker environments.

   .. rubric:: 3.15.0 (2026-02-28)

   * Feature: Add ``investigation_type`` handling to ES findings.

   .. rubric:: 3.14.0 (2026-02-27)

   * Feature: Add filename and file-size data to ES findings.
   * Feature: Update ES finding creation to handle related containers and vault records.

   .. rubric:: 3.13.0 (2026-02-24)

   * Feature: Add support for ES entity containers.

   .. rubric:: 3.12.0 (2026-02-24)

   * Feature: Add bulk ES finding creation.
   * Feature: Add support for saving email attachments to a container's vault.

   .. rubric:: 3.11.2 (2026-02-24)

   * Fix: Preserve raw fields when initializing ``PermissiveActionOutput``.

   .. rubric:: 3.11.1 (2026-02-23)

   * Fix: Add serialization support for permissive action outputs.

   .. rubric:: 3.11.0 (2026-02-20)

   * Feature: Allow apps to use permissive outputs that skip Pydantic validation.

   .. rubric:: 3.10.1 (2026-02-18)

   * Fix: ES polling through Automation Broker and improve the polling workflow.

   .. rubric:: 3.10.0 (2026-02-10)

   * Feature: Add attachment uploads to ES findings polling.
   * Feature: Improve ES findings polling triggers and use the Splunk ES proxy for
     communication.
   * Feature: Use optional syntax for polling parameters.

   .. rubric:: 3.9.1 (2026-02-04)

   * Fix: Use optional type syntax for polling parameters.

   .. rubric:: 3.9.0 (2026-02-03)

   * Fix: Allow optional type annotations in parameters and fields.
   * Feature: Use modern union syntax in ``soarapps convert`` output.
   * Fix: Omit redundant ``required=True`` values from generated code.

   .. rubric:: 3.8.2 (2026-01-26)

   * Fix: The ES finding model and its usage.

   .. rubric:: 3.8.1 (2026-01-22)

   * Fix: Make ``OutputField`` optional by default.

   .. rubric:: 3.8.0 (2026-01-21)

   * Feature: Add the ``is_file`` option to ``AssetField`` for file uploads.

   .. rubric:: 3.7.0 (2025-12-18)

   * Feature: Add OAuth authentication flows and standardize SDK authentication types.
   * Feature: Improve webhook redirect URL generation and state handling.
   * Feature: Add category metadata to asset fields.

   .. rubric:: 3.6.1 (2025-12-15)

   * Fix: Manifest paths when building an app from source-built wheels.

   .. rubric:: 3.6.0 (2025-12-12)

   * Feature: Add a client for submitting ES findings.
   * Feature: Update ES polling to use the new workflow.
   * Feature: Allow package builds to use a local SDK directory.
   * Feature: Add ``supports_es_polling`` to generated app manifests.

   .. rubric:: 3.5.0 (2025-12-05)

   * Feature: Add email-processing helpers for RFC 5322 messages.
   * Fix: Improve URL extraction and forwarded-message parsing.

   .. rubric:: 3.4.0 (2025-12-04)

   * Feature: Add poll metadata that distinguishes immediate polling from scheduled
     polling.

   .. rubric:: 3.3.2 (2025-12-03)

   * Fix: Support all Python 3.14.x versions instead of only Python 3.14.0.

   .. rubric:: 3.3.1 (2025-12-03)

   * Fix: Custom view handling.

   .. rubric:: 3.3.0 (2025-12-02)

   * Feature: Add SDK command-line testing tools and a Model Context Protocol (MCP)
     testing tool.
   * Feature: Expand test options for actions, polling, webhooks, asset state, and
     Automation Broker integrations.

   .. rubric:: 3.2.3 (2025-11-25)

   * Fix: Update ``MarkupSafe`` for Python 3.14-compatible wheels.

   .. rubric:: 3.2.2 (2025-11-19)

   * Fix: Dependency resolution when a specific Python version is selected.
   * Fix: Use standard packaging specifiers and preserve indentation in generated
     multiline code.

   .. rubric:: 3.2.1 (2025-11-06)

   * Fix: Selection of compatible ``abi3`` wheels.

   .. rubric:: 3.2.0 (2025-10-30)

   * Feature: Add the ``on_es_poll`` action type and example app support.
   * Feature: Add support for sending findings to Splunk Enterprise Security.

   .. rubric:: 3.1.0 (2025-10-27)

   * Feature: Add an ES Finding model for platform and SDK use.

   .. rubric:: 3.0.0 (2025-10-27)

   **Breaking changes:**

   * Feature: Upgrade to Pydantic 2 and remove Pydantic 1 support. Apps that use Pydantic
     1 APIs must migrate their validators, model configuration, and field access
     before upgrading. For example, replace ``@validator``, ``class Config``, and
     ``__fields__`` with Pydantic 2 equivalents such as ``@field_validator``,
     ``model_config``, and ``model_fields``.
   * Feature: Support only Python 3.13 and 3.14. Update the app's Python requirement and
     runtime; Python 3.9 through 3.12 are no longer supported.
   * Feature: Require Splunk SOAR 7.0.0 or later. Upgrade the target Splunk SOAR
     environment before using SDK 3.x.

.. dropdown:: SDK 2

   .. rubric:: 2.3.7 (2025-10-22)

   * Fix: Improve legacy ``phantom`` compatibility by isolating the import in the SDK
     shim.

   .. rubric:: 2.3.6 (2025-10-21)

   * Fix: SDK paths when an app runs through Automation Broker.

   .. rubric:: 2.3.5 (2025-10-18)

   * Fix: Allow optional action fields in input specifications.

   .. rubric:: 2.3.4 (2025-10-10)

   * Fix: Generate a pre-commit configuration template and a release-notes directory
     during ``soarapps init``.

   .. rubric:: 2.3.3 (2025-10-10)

   * Fix: Clarify parameter descriptions for the Make Request action.

   .. rubric:: 2.3.2 (2025-10-10)

   * Fix: Require release notes in app packages used for app updates and new-app
     flows.
   * Fix: Represent Python versions as strings in generated metadata.

   .. rubric:: 2.3.1 (2025-10-07)

   * Fix: Improve Make Request handling and preserve empty action messages instead of
     substituting placeholder text.

   .. rubric:: 2.3.0 (2025-10-02)

   * Feature: Add column names and ordering metadata to action parameters.

   .. rubric:: 2.2.0 (2025-10-01)

   * Feature: Add the ``render_as`` option for action output rendering.

   .. rubric:: 2.1.1 (2025-09-30)

   * Fix: List-valued action output handling.

   .. rubric:: 2.1.0 (2025-09-26)

   * Feature: Allow actions to enable concurrency locks.

   .. rubric:: 2.0.1 (2025-09-25)

   * Fix: Serialization and deserialization of nested list and optional types.

   .. rubric:: 2.0.0 (2025-09-24)

   **Breaking changes:**

   * Feature: Rename the generic action API to Make Request. Change
     ``app.generic_action()`` to ``app.make_request()``, rename
     ``GenericActionParams`` and ``GenericActionOutput`` to
     ``MakeRequestParams`` and ``MakeRequestOutput``, and update any manifest or
     action references from ``generic_action`` to ``make_request``.
   * Feature: Remove the deprecated ``ActionOutput.generate_action_summary_message()``
     method. Apps that call or override it must set action messages with
     ``SOARClient.set_message()`` instead.
   * Feature: Restore string-based view-handler references in generated manifests. Apps
     that register view handlers as callables must switch to import strings.

.. dropdown:: SDK 1

   .. rubric:: 1.6.3 (2025-09-23)

   * Fix: Allow ``ActionOutput`` to be optional.

   .. rubric:: 1.6.2 (2025-09-22)

   * Fix: An edge case when decrypting sensitive action parameters.

   .. rubric:: 1.6.1 (2025-09-18)

   * Fix: A broken link in the SDK documentation.

   .. rubric:: 1.6.0 (2025-09-18)

   * Feature: Add a method to retrieve the asset ID from the SOAR client.

   .. rubric:: 1.5.3 (2025-09-18)

   * Fix: Document Splunk SOAR version compatibility and update documentation
     examples.

   .. rubric:: 1.5.2 (2025-09-17)

   * Fix: Increase connection and read timeouts for ``soarapps install``.

   .. rubric:: 1.5.1 (2025-09-16)

   * Fix: Add the missing ``ActionResult.get_message()`` compatibility shim.
   * Fix: Remove the obsolete ``order`` argument from the ``Param`` documentation.

   .. rubric:: 1.5.0 (2025-09-11)

   * Feature: Allow actions to be registered with import strings.
   * Fix: Preserve full view-handler import paths in generated manifests.

   .. rubric:: 1.4.1 (2025-09-10)

   * Fix: Improve app conversion by preserving asset value types and using default
     Python versions.
   * Fix: Treat action parameters as optional by default during deserialization.
   * Fix: Normalize field names and create aliases for names that are not valid Python
     identifiers.

   .. rubric:: 1.4.0 (2025-09-10)

   * Feature: Add a method to retrieve the container ID from the SOAR client.

   .. rubric:: 1.3.4 (2025-09-09)

   * Fix: Improve documentation generation and style validation.

   .. rubric:: 1.3.3 (2025-09-08)

   * Fix: Standardize Splunk SOAR terminology throughout the documentation.

   .. rubric:: 1.3.2 (2025-09-07)

   * Fix: Write error-level logs to the error log.
   * Fix: Use ``soar`` as the canonical parameter name for the SOAR client in
     generated examples.
   * Fix: Improve the Getting Started and API Reference documentation.

   .. rubric:: 1.3.1 (2025-09-05)

   * Fix: Add the CLI Reference and improve the documentation site's presentation.

   .. rubric:: 1.3.0 (2025-09-05)

   * Feature: Allow actions to set a result summary and message.
   * Feature: Warn when code uses the older action-message APIs.
   * Fix: Add successful-object totals to action output metadata.

   .. rubric:: 1.2.3 (2025-09-02)

   * Fix: Correct documentation issues.

   .. rubric:: 1.2.2 (2025-09-02)

   * Fix: Build the Splunk SDK from source when a compatible wheel is unavailable.

   .. rubric:: 1.2.1 (2025-08-28)

   * Fix: Use field aliases when serializing action outputs.

   .. rubric:: 1.2.0 (2025-08-28)

   * Feature: Allow actions to return iterable values containing multiple outputs.

   .. rubric:: 1.1.0 (2025-08-22)

   * Feature: Add a timezone type for asset parameters.

   .. rubric:: 1.0.2 (2025-08-21)

   * Fix: Correct package metadata and badges for the Python version and PyPI
     stability.

   .. rubric:: 1.0.1 (2025-08-21)

   * Fix: Maintenance release with no user-facing SDK behavior changes.

   .. rubric:: 1.0.0 (2025-08-21)

   * Feature: Initial stable release of the Splunk SOAR SDK.
   * Feature: Provide typed app and action definitions, manifest generation, CLI-based
     packaging and testing, compatibility shims, polling, webhooks,
     authentication, asset state, and documentation.
