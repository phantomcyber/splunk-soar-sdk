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

This package contains all the code and metadata for your app. It also contains all the dependency wheels for your app, which are sourced from the PyPI CDN based on ``uv.lock``.

Because of this, you should ensure that your ``uv.lock`` is always up to date.

Installing and Running the App
------------------------------

Now you can install the app in your Splunk SOAR platform to test how it works. You can do this by using the web interface of the platform.

You can also do this from the command line::

    soarapps package install myapp.tgz soar.example.com

Getting Help
============

If you need help, please file a GitHub issue at https://github.com/phantomcyber/splunk-soar-sdk/issues.

Next Steps
==========

Now that you have a working app, you can start its development. Here's what you can check next when working with the app you create:

- :ref:`Asset Configuration <asset-configuration-label>`
- :ref:`Action Parameters <action-param-label>`
- :ref:`Action Outputs <action-output-label>`
