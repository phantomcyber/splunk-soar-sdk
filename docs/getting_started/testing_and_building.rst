.. _testing-and-building-app:

Testing and Building the App
============================

Running From the Command Line
-----------------------------

You can run any of your app's actions directly in your CLI, without installing a full copy of Splunk SOAR. Simply invoke the Python file that contains your app::

    python src/app.py action my-action -p test_params.json -a test_asset.json

You should provide a parameters file (``-p``) which contains the JSON-encoded parameters for your action. The asset file (``-a``) contains the asset config in JSON format.

This command will run your action on your local machine, and print its output to the command line.

Building an App Package
-----------------------

Run ``soarapps package build`` to generate an app package. By default, this creates ``<appname>.tgz`` in the root directory of your app.

The package contains your app's code, metadata, and dependency wheels. The build
downloads dependencies from the URLs in ``uv.lock`` and verifies their checksums.
Keep ``uv.lock`` up to date when you change dependencies or switch registries.

For a private index, the build reads the index configuration from uv's project,
user, and system configuration files. It supports credentials in the configured
index URL and the ``UV_INDEX_<NAME>_USERNAME`` and ``UV_INDEX_<NAME>_PASSWORD``
environment variables for named indexes. It can also read credentials from the
file named by ``NETRC`` or from ``~/.netrc`` when ``NETRC`` is unset.
The build sends those credentials only to artifact URLs on the same scheme,
host, and port as the locked index.

Installing and Running the App
------------------------------

Now you can install the app in your Splunk SOAR platform to test how it works. You can do this by using the web interface of the platform.

You can also do this from the command line::

    soarapps package install myapp.tgz soar.example.com

TLS certificates are verified by default. If the Splunk SOAR instance does not have a valid certificate, pass ``--insecure`` to explicitly disable certificate verification.

Getting Help
============

If you need help, please file a GitHub issue at https://github.com/phantomcyber/splunk-soar-sdk/issues.

Next Steps
==========

Now that you have a working app, you can start its development. Here's what you can check next when working with the app you create:

- :ref:`Asset Configuration <asset-configuration-label>`
- :ref:`Action Parameters <action-param-label>`
- :ref:`Action Outputs <action-output-label>`
