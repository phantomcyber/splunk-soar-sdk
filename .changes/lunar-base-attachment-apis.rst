* Feature: Add the ``soar.attachments`` API to request Lunar Base attachment
  upload targets and queue finding-to-attachment associations through the
  ingestion runtime bridge, validating unique attachment IDs and reporting
  runtime failures as ``AttachmentApiError`` without exposing upstream errors
  in tracebacks.
