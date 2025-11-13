# Integration Tests

This directory contains integration tests for the SOAR SDK example applications.

## Overview

The integration tests verify that the SDK-built apps can be installed and run correctly on actual SOAR instances. Currently, the tests focus on:

1. **Example App** - Basic SDK app testing
   - Test connectivity action

2. **Example App with Webhook** - Webhook-enabled SDK app testing
   - Test connectivity action

## Test Structure

- `phantom_constants.py` - Constants for Phantom REST API endpoints and statuses
- `phantom_instance.py` - Helper class for interacting with Phantom instances
- `test_example_app.py` - Integration tests for the basic example app
- `test_example_app_with_webhook.py` - Integration tests for the webhook example app
- `conftest.py` - Pytest configuration

## Running Tests Locally

To run the integration tests locally, you need:

1. Access to a SOAR instance
2. Set the required environment variables:
   ```bash
   export PHANTOM_URL="https://your-instance-url"
   export PHANTOM_USERNAME="admin"
   export PHANTOM_PASSWORD="your-password"
   ```

3. Install the apps on the instance first:
   ```bash
   # Build the apps
   cd tests/example_app
   uv run soarapps package build . --output-file /tmp/example_app.tgz

   cd ../example_app_with_webhook
   uv run soarapps package build . --output-file /tmp/example_app_with_webhook.tgz

   # Install them using the REST installer
   python .github/utils/app_rest_installer.py /tmp/example_app.tgz <phantom_ip> <username> <password>
   python .github/utils/app_rest_installer.py /tmp/example_app_with_webhook.tgz <phantom_ip> <username> <password>
   ```

4. Run the integration tests:
   ```bash
   uv run pytest tests/integration/ -v
   ```

## CI/CD Integration

The integration tests run automatically in the GitHub Actions workflow `.github/workflows/integration_tests.yml` on:
- Push to main, next, or beta branches
- Pull requests

The workflow:
1. Builds both example apps
2. Installs them on test SOAR instances (previous and next versions)
3. Runs the integration tests
4. Reports results

## Adding New Tests

To add new integration tests:

1. Create a new test file in this directory (e.g., `test_new_feature.py`)
2. Use the `phantom_instance` fixture to interact with the SOAR instance
3. Follow the existing test patterns for setup/teardown
4. Run tests locally to verify before committing

Example test structure:
```python
import pytest
from .phantom_instance import PhantomInstance
from .phantom_constants import ACTION_TEST_CONNECTIVITY

@pytest.fixture(scope="module")
def phantom_instance():
    # Setup connection to instance
    pass

def test_my_action(phantom_instance):
    # Test your action
    pass
```

## Test Coverage

Current test coverage:
- ✅ Test connectivity for example_app
- ✅ Test connectivity for example_app_with_webhook
- 🔲 On-poll action testing (future)
- 🔲 Webhook ingestion testing (future)
- 🔲 Custom action testing (future)
