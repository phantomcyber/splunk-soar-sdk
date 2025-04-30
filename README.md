# Splunk SOAR SDK - the official tool for Splunk SOAR app development

# Installation

The Splunk SOAR SDK is available as [a package on PyPI](https://pypi.org/project/splunk-soar-sdk/).

The recommended installation method is via [uv](https://docs.astral.sh/uv/).

## Installing the SDK as a tool

This package defines the `soarapps` command line interface. To use it, [install as a uv tool](https://docs.astral.sh/uv/guides/tools/):

```shell
uv tool install splunk-soar-sdk
soarapps --help
```

## Installing the SDK as an app dependency

When developing a new Splunk SOAR app using the SDK, you should use [uv](https://docs.astral.sh/uv/) as your project management tool:

```shell
uv add splunk-soar-sdk
```

Running the above command will add `splunk-soar-sdk` as a dependency of your Splunk SOAR app, in your `pyproject.toml` file.

# Usage

In order to start using SDK and build your first Splunk SOAR App, follow the [Getting Started guide](/docs/getting_started.md).

A Splunk SOAR app developed with the SDK will look something like this:

Project structure:
```
string_reverser/
├─ src/
│  ├─ __init__.py
│  ├─ app.py
├─ tests/
│  ├─ __init__.py
│  ├─ test_app.py
├─ .pre-commit-config.yaml
├─ logo.svg
├─ logo_dark.svg
├─ pyproject.toml
```

With `app.py` containing:
```python
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.params import Params
from soar_sdk.action_results import ActionOutput


class Asset(BaseAsset):
    base_url: str
    api_key: str = AssetField(sensitive=True, description="API key for authentication")


app = App(asset_cls=Asset)


@app.test_connectivity()
def test_connectivity(client: SOARClient, asset: Asset) -> None:
    client.debug(f"testing connectivity against {asset.base_url}")


class ReverseStringParams(Params):
    input_string: str


class ReverseStringOutput(ActionOutput):
    reversed_string: str


@app.action(action_type="test", verbose="Reverses a string.")
def reverse_string(
    param: ReverseStringParams, client: SOARClient
) -> ReverseStringOutput:
    reversed_string = param.input_string[::-1]
    return ReverseStringOutput(reversed_string=reversed_string)


if __name__ == "__main__":
    app.cli()
```

# Requirements

* [uv](https://docs.astral.sh/uv/getting-started/installation/)
* Python >=3.9
  * Python may be installed locally [with uv](https://docs.astral.sh/uv/guides/install-python/)
* Splunk SOAR >=6.4.0
  * You can get Splunk SOAR Community Edition from [the Splunk website](https://www.splunk.com/en_us/products/splunk-security-orchestration-and-automation.html)


---

Copyright 2025 Splunk Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
