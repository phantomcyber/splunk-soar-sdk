* Fix: Breaking: The SDK uses the maintained HTTPX2 client. Replace ``httpx``
  with ``httpx2`` for clients, auth, timeouts, transports, and exceptions used
  with the SDK, update HTTP mocks, then regenerate your app lockfile and rebuild
  the app. HTTPX2 uses the operating system's CA store by default and honors
  ``SSL_CERT_FILE`` and ``SSL_CERT_DIR``.
