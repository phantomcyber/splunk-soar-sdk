* Feature: Add runtime-bound ES finding creation and polling with typed models,
  per-finding outcomes, attachment upload targets, bounded parallel file uploads,
  and queued finding-to-attachment associations. Preserve classic SOAR behavior
  and report safe errors without exposing runtime credentials or file contents.
  Adapt existing Finding dashboard identities and token mappings to the ES format.
  Checkpoint successful ES polling batches and retain failed batches for replay.
  Apply ES ingest settings supplied as polling parameters by the execution runtime.
  Reject immediate analysis or automation with local polling attachments until
  attachment readability is guaranteed, retaining failed batches for replay.
  Preserve asset-qualified finding sources across classic and direct polling.
