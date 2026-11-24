Installation
============

The Splunk SOAR Apps SDK is useful both as a CLI tool, for creating and managing Splunk SOAR apps, and as a Python library for building such apps. In both cases, the preferred installation method is via ``uv``. This section covers the installation steps for the SDK as a CLI tool. The CLI tool can be used to quickly initialize a new Splunk SOAR app project, which will automatically depend on the SDK library.


Prerequisites
-------------

- A Mac or Linux machine. Windows is not supported.
- Git installed and available in your PATH.
- `uv <https://docs.astral.uv/>`_: the Python version and environment manager used by the SDK.
- It's recommended to also install ``ruff`` and ``pre-commit``, as these are often used when building Splunk SOAR apps:
    .. code-block:: bash

        uv tool install ruff
        uv tool install pre-commit --with pre-commit-uv


Installing the SDK as a Tool
----------------------------

The SDK can be installed and used as a command-line interface (CLI) tool, accessible via the ``soarapps`` command. This allows you to create, test, and manage Splunk SOAR apps directly from your terminal. To install the CLI tool, use the following command:
    .. code-block:: bash

        uv tool install splunk-soar-sdk

Once installed, you can access the CLI using the command:
    .. code-block:: bash

        soarapps --help

This provides a range of commands to help you develop and manage your Splunk SOAR apps efficiently. A full reference is available in the :ref:`CLI Reference <cli_reference>` section of this documentation.

Import behavior
---------------

On Python 3.15, SDK modules defer their imports until the imported names are
used. Python 3.13 keeps its eager import behavior. Logging setup and optional
SOAR platform fallbacks continue to run when their modules load.

The SDK uses module-local ``__lazy_modules__`` declarations and preserves the
application's interpreter-wide lazy-import mode and filter. To troubleshoot
an import-order issue on Python 3.15, set an eager-import filter before importing
the SDK:

.. code-block:: python

    import sys

    sys.set_lazy_imports_filter(lambda importer, imported, fromlist: False)

Upgrading connectors to HTTPX2
------------------------------

The SDK's HTTP clients and authentication helpers use HTTPX2. Update your app's
HTTP dependency and imports to ``httpx2`` wherever the app works with SDK HTTP
clients. Use ``httpx2[http2]`` if your app enables HTTP/2.

Update custom auth classes, injected clients, transports, timeouts, and
exception handlers to use the corresponding HTTPX2 types. If you intercept SDK
requests in tests, configure the mocks for HTTPX2.

HTTPX2 uses the operating system's CA store by default. For private CAs,
configure ``SSL_CERT_FILE`` or ``SSL_CERT_DIR``, or pass an ``ssl.SSLContext``
when you create your client.

Regenerate the lockfile and rebuild the package from your app directory.

.. code-block:: bash

    uv lock
    soarapps package build
