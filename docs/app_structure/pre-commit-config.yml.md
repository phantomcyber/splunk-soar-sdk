# `.pre-commit-config.yml` default file contents

This file is to be used with [pre-commit](https://pre-commit.com) tool. It adds some automation to
the process of committing changes when developing the app.

In the file you will find the definitions of the hooks that it installs with `pre-commit` command.

You may notice it adds hooks from the official Splunk SOAR `dev-cicd-tools` repository. These are
helping with the process of the apps development, like [building wheel dependencies](/docs/getting_started.md#building-dependencies-wheels).

When working on your app in the long run, you should check every once in a while if this hooks repository
had a newer release and update your version accordingly.
