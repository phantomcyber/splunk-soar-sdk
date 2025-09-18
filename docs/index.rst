Splunk SOAR SDK Documentation
=============================

The Splunk SOAR SDK is the official tool and library for building connectors that integrate with Splunk SOAR. You can use it to create new apps, convert old-style apps to the new format, and test your apps locally before deploying them to a Splunk SOAR instance.

If you want to learn more about how to use the SDK, check out the following resources:

- :ref:`Getting Started <getting_started_index>`: A step-by-step guide to creating your first Splunk SOAR app using the SDK.
- :ref:`App Structure <app-structure>`: Detailed information on the structure of a Splunk SOAR app and its components.
- :ref:`API Reference <api_reference>`: Comprehensive reference for the SDK's Python API.
- :ref:`CLI Reference <cli_reference>`: Documentation for the SDK's command-line interface (CLI) tool.

If you find bugs, need help, or have suggestions, please visit the `Splunk SOAR SDK GitHub repository <https://github.com/phantomcyber/splunk-soar-sdk>`_ and file an issue.


What is a Splunk SOAR App and What are Actions?
-----------------------------------------------

Apps (aka Connectors) in Splunk SOAR are extensions that enrich the platform functionality. Each app provides a new set of actions that can be used to automate security investigations and response. Usually, a single app adds actions which integrate with a specific tool or 3rd party service (e.g. whois lookup or geolocation).

This SDK is a set of tools to build, test and run your own app that will extend Splunk SOAR by implementing actions which integrate with 3rd parties.

Splunk SOAR Compatibility
=========================

The Splunk SOAR SDK codifies its minimum supported Splunk SOAR version under ``soar_sdk.compat.MIN_PHANTOM_VERSION``:

.. literalinclude:: ../src/soar_sdk/compat.py
    :language: python
    :start-at: MIN_PHANTOM_VERSION =
    :end-at: MIN_PHANTOM_VERSION =


By default, any Splunk SOAR app developed with this version of the SDK will run on all released Splunk SOAR versions above that minimum*.

Both Splunk SOAR Cloud and Splunk SOAR On-Prem are supported at this defined minimum version and above.

.. note::

   \* Forward-compatibility is not guaranteed, but is strived for. Backward-compatibility is guaranteed down to the ``MIN_PHANTOM_VERSION``

Contents
========

.. toctree::
   :maxdepth: 4

   getting_started/index
   app_structure/index
   custom_views/index
   api_reference
   cli_reference
   changelog


Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
