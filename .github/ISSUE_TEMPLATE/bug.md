---
name: Bug
about: Report a bug in the SDK
title: 'Bug: <summary of bug>'
labels: ''
assignees: ''

---

## Describe the bug
A clear and concise description of what the bug is.

## Tell us how to reproduce it
Clear and concise steps to reproduce the issue.
- If the issue is related to your app code, please include it in the **Example code** section.
- If the issue is related to initializing, building, or testing an app from the command line, please include the commands you are running, and any relevant output.
- If the issue is related to installing or running an app in Splunk SOAR, please provide the following:
  - Splunk SOAR platform version
  - Is this an on-premises or SOAR Cloud deployment?
  - For on-prem deployments, the OS name and version
  - Automation Broker version, if any

### Expected behavior
A clear and concise description of what you expected to happen.

### Actual behavior
A clear and concise description of what actually happened.

## Example code
Please attach any code related to the issue. A [Minimal, Reproducible Example](https://stackoverflow.com/help/minimal-reproducible-example) is most helpful.

If the code is only a function or two, you can paste it in the block below:
```python
@app.action()
def my_action():
    pass
```

If it is larger, please attach it as a file, or link to it from your own repository.

## Additional context
Add any other context about the problem here.

## Logs
Please attach any relevant entries from `spawn.log`, `app_interface.log`, or `app_install.log`.

For on-prem deployments, these can be found in `/opt/phantom/var/log/phantom/`.

For Cloud deployments, they can be downloaded from the `Administration -> System Health -> Debugging` page.
