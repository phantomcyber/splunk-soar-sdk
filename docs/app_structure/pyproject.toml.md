# `pyproject.toml` default file contents

The `pyproject.toml` file is the core information source on the app and its development.
It can be [used as usual](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
when building python packages. For the purposes of the SOAR app development, we are also using poetry
with this file for managing the dev environment and dependencies. Additionally, the file contains
section (table) with meta information needed for generating the [SOAR App Manifest](/docs/app_manifest.md).

The file contents provide:
- basic application info (e.g. name, version, description)
- dependencies - which SDK uses for building the app dependency wheels
- soar app Manifest information - the data required for creating the app Manifest (e.g. appid, type )

Here's the example file contents for starting app:

```toml
[tool.poetry]
name = "Example Application"
version = "0.0.1"
description = "This is the basic example SOAR app"
license = "Copyright"
authors = [
    "John Doe <email@domain.com>",
]
readme = "README.md"
homepage = "https://www.splunk.com/en_us/products/splunk-security-orchestration-and-automation.html"
packages = [{include = "src"}]

[tool.poetry.dependencies]
python = ">=3.9, <3.10"
splunk-soar-sdk = "^0.0.0"

[tool.poetry.group.dev.dependencies]
pre-commit = "3.7.0"
coverage = "^7.6.7"
mypy = "1.2.0"
pytest = "7.4.2"
pytest-mock = "^3.14.0"
pytest-watch = "^4.2.0"
ruff = "^0.7.4"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[virtualenvs]
in-project = true

[tool.soar.app]
appid = "1e1618e7-2f70-4fc0-916a-f96facc2d2e4"
type = "sandbox"
product_vendor = "Splunk"
logo = "logo.svg"
logo_dark = "logo_dark.svg"
product_name = "Example App"
python_version = "3"
product_version_regex = ".*"
publisher = "Splunk"
min_phantom_version = "6.2.2.134"
app_wizard_version = "1.0.0"
fips_compliant = false
main_module = "src.app:app"
```

# Decomposing file contents

Most of the information in the file follow [the standards of writing the `pyproject.toml` file](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).
We will focus now on some parts specific to the SDK use.

In `[tool.poetry.dependencies]` table you should put `splunk-soar-sdk` dependency as you will need it not only for
developing the app, but also it is needed for running it. When creating your new app, make sure to use the newest
SDK version compatible with the SOAR platform you are using.

Currently, the only supported python version is 3.9, which is the same as the one available on SOAR platform.

The `[tool.poetry.group.dev.dependencies]` should contain the following libraries that will be used for
the app development:
- `pre-commit` - used for running linting checks, wheels building, and testing apps in the SOAR infrastructure
- `pytest` - necessary for writing tests for your app that can be run independently of the SOAR platform (also locally)
- `pytest-mock` - needed for mocking some functionality in testing, especially the SOAR engine libraries

The following packages are optional, but strongly recommended for following the good practices
and keeping your app maintainable:
- `mypy` for taking care of static type checking
- `pytest-watch` for constantly running tests while developing (e.g. in TDD)
- `ruff` for linting and formatting the code ([check more](https://github.com/astral-sh/ruff))

## SOAR App information table

In `[tool.soar.app]` you will put all necessary configuration for the app, which will be mainly used
for creating Manifest file and then running the app in the SOAR platform.

All the keys provided above for the table are required. You can find their description and possible values
in the [SOAR documentation page](https://docs.splunk.com/Documentation/SOAR/current/DevelopApps/Metadata)

# Next steps

In the next step, you should get familiar with the [`app.py` application source code file contents](./app.py.md).

# Related pages

- [App configuration](/docs/app_configuration.md)
- [Continuous Integration for SOAR Apps](/docs/cicd_tools.md)
- [App Manifest](/docs/app_manifest.md)
