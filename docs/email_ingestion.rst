Bounded Email Ingestion
=======================

Mailbox data is untrusted input. Connectors that poll email must bound raw-message
parsing, decoded attachments, nesting, and persisted bytes so one message cannot
exhaust worker memory, temporary storage, or the SOAR vault. The low-level
``extract_email_data`` helper remains available for compatibility, but it does not
enforce these limits. Polling and ingestion code should use ``analyze_email``.

The shared defaults are 150 MiB for the selected raw email root, 25 MiB for one
decoded leaf attachment, 100 MiB and 100 files for all decoded leaf attachments
under one root, ten levels of attached-email nesting, and 250 MiB of projected
persisted data per poll invocation. A value equal to a limit is accepted. Asset
fields use binary mebibytes: one configured MiB is 1,048,576 bytes.

Asset configuration
-------------------

Add ``EmailBudgetAssetMixin`` before ``BaseAsset`` so every email connector exposes
the same optional ingest fields and validation:

.. code-block:: python

   from soar_sdk.asset import BaseAsset
   from soar_sdk.extras.email import EmailBudgetAssetMixin


   class Asset(EmailBudgetAssetMixin, BaseAsset):
       server: str


The mixin rejects zero and negative values, a per-attachment limit greater than the
per-email aggregate, and a poll limit too small to hold one otherwise-valid maximum
message.

Safe analysis
-------------

``analyze_email`` preserves the selected raw evidence as bytes and returns only
attachments accepted by the configured count and decoded-size budgets:

.. code-block:: python

   from soar_sdk.extras.email import analyze_email


   limits = asset.email_budget_limits()
   result = analyze_email(raw_message, limits=limits, email_id=provider_id)

   if result.root is None:
       # The raw root exceeded its parser limit. Publish a metadata-only partial
       # result using result.fallback_metadata and result.warnings.
       ...
   else:
       # Persist only result.root_raw and result.retained_attachments.
       ...


For an ordinary message, the incoming message is the analysis root. When a
forwarding envelope contains an attached ``.eml``, ``.msg``, or
``message/rfc822`` message, that attached message becomes the root and the outer
message is returned as reporter metadata. This prevents the forwarding wrapper
from consuming the suspicious message's attachment budget. If multiple valid
attached roots are present, the first in MIME order is selected, additional roots
are handled as ordinary attachments, and the result is visibly marked incomplete.

Message-limit violations are terminal partial results. The connector should create
the container or finding, apply the standardized warnings, and advance its message
checkpoint. Retrying an intrinsically oversized message forever would block the
mailbox.

Warning presentation
--------------------

Use the presentation helper that matches the polling mode:

.. code-block:: python

   from soar_sdk.extras.email import (
       apply_warnings_to_container,
       apply_warnings_to_finding,
   )


   apply_warnings_to_container(container, result.warnings)
   apply_warnings_to_finding(finding, result.warnings)


The helpers preserve the connector's existing description and metadata. They add a
clear analyst-facing warning plus structured ``email_analysis`` data. Containers
also receive ``Email Analysis Warning`` artifacts so downstream playbooks can
distinguish a clean result from incomplete analysis.

Transactional poll budget
-------------------------

``EmailPollBudget`` protects bytes that would actually be persisted during one
poll. Analyze and stage the complete email before yielding any container or
finding. If it does not fit, emit only ``deferral_message``, create no container,
finding, artifact, or vault record, leave the checkpoint immediately before that
email, and stop the poll. Commit the projected bytes only after the generator
resumes following successful persistence:

.. code-block:: python

   from soar_sdk.extras.email import EmailPollBudget


   poll_budget = EmailPollBudget(limits)
   result = analyze_email(raw_message, limits=limits, email_id=provider_id)

   if not poll_budget.can_commit(result.projected_persisted_bytes):
       soar.debug(poll_budget.deferral_message(provider_id))
       return

   yield container_or_finding
   poll_budget.commit(result.projected_persisted_bytes)
   update_checkpoint(provider_id)


Polling deferral is scheduling behavior, not an analysis warning. Never copy its
message into a published container or finding; the same email is retried with a
fresh poll budget on the next invocation.
