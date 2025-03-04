Splunk SOAR Apps SDK - a tool for fast and clean SOAR Apps development

# Requirements

The SDK enables developing, testing and running the Splunk SOAR Apps written in Python. As such
it has some prerequisites in order to run:

1. Python 3.9 - all SOAR Apps are running in Python 3.9 environment and they should be developed in such.
  You can provide it in the way that suits you the best. You can use [system installer](https://www.python.org/downloads)
  or [pyenv](https://github.com/pyenv/pyenv).
1. Poetry - each app is developed with [poetry tool](https://python-poetry.org/) so you will need to have it installed locally for your python installation.
1. Splunk SOAR 6.4.0+ - apps built with this SDK are supported by SOAR starting from version 6.4.0.  You can [get your Splunk SOAR from the Splunk website](https://www.splunk.com/en_us/products/splunk-security-orchestration-and-automation.html).

# Installation

Splunk SOAR Apps SDK is available as [a package on PyPI](MISSING_LINK). It should be installed
as one of the dependencies in your Splunk SOAR App using poetry (see the _Creating the SOAR App_ section below).

# Getting started

In order to start using SDK and build your first SOAR App, follow the [Getting Started guide](/docs/getting_started.md).
