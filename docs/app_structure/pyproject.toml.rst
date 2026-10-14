.. _app-structure-pyproject:

``pyproject.toml``
==================

The ``pyproject.toml`` is a `standardized file <https://packaging.python.org/en/latest/guides/writing-pyproject-toml/>`_ for python projects, which contains critical metadata about your app and its dependencies.

The file contains:

- Basic application info (e.g. name, version, description)
- Dependencies, which are managed automatically by `uv <https://docs.astral.sh/uv/guides/projects/#managing-dependencies>`_
- The import path for your app's :class:`~soar_sdk.app.App` instance.
- Settings for various development tools (e.g. linters and formatters)

Here's an example for a first app:

.. code-block:: toml

    [project]
    name = "my_first_app"
    version = "0.0.1"
    description = "My first app"
    license = "Apache-2.0"
    requires-python = ">=3.13, <3.16, !=3.14.*"
    authors = [ "Me", "Myself", "I" ]
    dependencies = [
        "splunk-soar-sdk",
    ]

    [tool.soar.app]
    main_module = "src.app:app"

    ### YOU SHOULD NOT NEED TO TOUCH ANYTHING BELOW THIS LINE ###

In general, you should only have to edit entries under the ``[project]`` section. If you need to add dependencies, use the `uv CLI tool <https://docs.astral.sh/uv/guides/projects/#managing-dependencies>`_ to do so (with ``uv add``).

Python version support
----------------------

The SDK supports Python 3.13 and 3.15. New apps target both versions by default.
Use ``soarapps init --python-version 3.13`` or ``--python-version 3.15`` to target
a single version and bundle only its dependency wheels.

To migrate an existing app from Python 3.14, update ``requires-python`` to
``">=3.13, <3.16, !=3.14.*"`` and replace ``3.14`` with ``3.15`` in the
``[tool.uv]`` environments and required-environments lists. Update any explicit
``App(python_version=...)`` values to use ``3.15`` or ``PythonVersion.PY_3_15``.
Run ``uv lock --upgrade`` to resolve dependencies with Python 3.15-compatible
Linux wheels, then rebuild the app with ``soarapps package build``. Generated
manifests now use ``pip315_dependencies`` and ``wheels/python315/``.
