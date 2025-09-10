.. _cli_reference:

CLI Reference
=============

The ``soarapps`` command-line tool is the main interface for working with Splunk SOAR apps from the command line. It provides commands for creating, building, and managing apps.

.. typer:: soar_sdk.cli.cli.app
    :prog: soarapps
    :width: 80
    :preferred: text
    :show-nested:
    :make-sections:

App CLI
-------

The :class:`~soar_sdk.app.App` class automatically generates a command-line interface (CLI) for your app. This CLI can be used to run actions (and verify their behavior) from the command line.

.. code-block:: console

    $ python src/app.py --help
    usage: app.py [-h] [--soar-url SOAR_URL] [--soar-user SOAR_USER] [--soar-password SOAR_PASSWORD] {action,webhook} ...

    positional arguments:
    {action,webhook}
        action              Run an action
        webhook             Invoke a webhook handler

    options:
    -h, --help            show this help message and exit
    --soar-url SOAR_URL   SOAR URL to connect to. Can be provided via PHANTOM_BASE_URL environment variable as well.
    --soar-user SOAR_USER
                            Username to connect to SOAR instance. Can be provided via PHANTOM_USER environment variable as well
    --soar-password SOAR_PASSWORD
                            Password to connect to SOAR instance. Can be provided via PHANTOM_PASSWORD environment variable as well


You can run any action defined in your app by using the ``action`` command. For example:

.. code-block:: console

    $ python src/app.py action my-action --help
    usage: app.py action my-action [-h] -p PARAMS_FILE -a ASSET_FILE

    optional arguments:
    -h, --help            show this help message and exit
    -p PARAMS_FILE, --params-file PARAMS_FILE
                            JSON file containing action parameters
    -a ASSET_FILE, --asset-file ASSET_FILE
                            JSON file containing asset configuration
