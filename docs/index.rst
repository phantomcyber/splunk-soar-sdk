Splunk SOAR SDK Documentation
=============================

The Splunk SOAR SDK is the official tool and library for building connectors that integrate with Splunk SOAR. You can use it to create new apps, convert old-style apps to the new format, and test your apps locally before deploying them to a SOAR instance.

If you want to learn more about how to use the SDK, check out the following resources:

- :ref:`Getting Started <getting_started_index>`: A step-by-step guide to creating your first SOAR app using the SDK.
- :ref:`App Structure <app-structure>`: Detailed information on the structure of a SOAR app and its components.
- :ref:`API Reference <api_reference>`: Comprehensive reference for the SDK's Python API.
- :ref:`CLI Reference <cli_reference>`: Documentation for the SDK's command-line interface (CLI) tool.

If you find bugs, need help, or have suggestions, please visit the `Splunk SOAR SDK GitHub repository <https://github.com/phantomcyber/splunk-soar-sdk>`_ and file an issue.


What is a SOAR app and what are actions?
----------------------------------------

Apps (aka Connectors) in Splunk SOAR are extensions that enrich the platform functionality. Each app provides a new set of actions that can be used to automate security investigations and response. Usually, a single app adds actions which integrate with a specific tool or 3rd party service (e.g. whois lookup or geolocation).

This SDK is a set of tools to build, test and run your own app that will extend SOAR by implementing actions which integrate with 3rd parties.

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


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
