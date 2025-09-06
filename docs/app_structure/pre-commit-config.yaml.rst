.. _app-structure-pre-commit:

``.pre-commit-config.yaml``
==========================

This file is the official configuration file for the `pre-commit <https://pre-commit.com>`_ tool. It adds some automation to
the process of committing changes when developing the app, and is a required file for all app repos in the official Splunk SOAR app Github organization. ``pre-commit`` is a framework for managing and maintaining multi-language pre-commit hooks. It helps ensure that code meets certain standards before it is committed to a repository, such as formatting, linting, and static security checks.

You should regularly run::

    pre-commit autoupdate

In your app repo to keep the pre-commit hooks up to date.
