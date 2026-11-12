* Feature: Add the ``soar.attachments`` API to request attachment upload
  targets, upload files individually or in bounded parallel batches, and queue
  finding-to-attachment associations through the ingestion runtime bridge,
  validating unique attachment IDs and reporting runtime failures as
  ``AttachmentApiError`` without retaining upstream exceptions or exposing
  their messages or raw upload credentials in SDK traceback locals.
