# Integration Tests Setup Checklist

Use this checklist to set up integration tests for the SDK repository.

## ✅ Setup Steps

### 1. Prepare SOAR Test Instances

- [ ] Identify a "previous" version SOAR instance (e.g., 6.3.x)
- [ ] Identify a "next" version SOAR instance (e.g., 6.4.x)
- [ ] Verify both instances are accessible from GitHub runners
- [ ] Test REST API access: `curl -k https://<instance-ip>/rest/version`

### 2. Create Service Account (if needed)

- [ ] Create or identify an admin user for testing
- [ ] Verify user has permissions to:
  - [ ] Install apps (`/app_install` endpoint)
  - [ ] Create/delete assets
  - [ ] Create/delete containers
  - [ ] Run actions

### 3. Configure GitHub Repository

Go to: **SDK Repository → Settings → Secrets and variables → Actions**

#### Variables Tab:
- [ ] Click "New repository variable"
- [ ] Add: `PHANTOM_INSTANCE_PREVIOUS_VERSION_IP` = `<previous-instance-ip>`
- [ ] Add: `PHANTOM_INSTANCE_NEXT_OL8_VERSION_IP` = `<next-instance-ip>`
- [ ] Add: `PHANTOM_USERNAME` = `admin` (or your service account username)
- [ ] (Optional) Add: `NUM_TEST_RETRIES` = `2`

#### Secrets Tab:
- [ ] Click "New repository secret"
- [ ] Add: `PHANTOM_PASSWORD` = `<your-secure-password>`

### 4. Verify Workflow Files

Check that these files exist in the repo:

- [ ] `.github/workflows/integration_tests.yml` - Main workflow
- [ ] `.github/utils/app_rest_installer.py` - App installer script
- [ ] `tests/integration/phantom_instance.py` - Instance helper
- [ ] `tests/integration/test_example_app.py` - Example app tests
- [ ] `tests/integration/test_example_app_with_webhook.py` - Webhook app tests

### 5. Test the Workflow

- [ ] Create a test branch: `git checkout -b test-integration-setup`
- [ ] Make a small change (e.g., add a comment)
- [ ] Push the branch: `git push origin test-integration-setup`
- [ ] Open a Pull Request
- [ ] Navigate to "Actions" tab in GitHub
- [ ] Find the "Integration Tests" workflow
- [ ] Watch it run and verify:
  - [ ] Build job completes (both apps built)
  - [ ] Integration test job starts
  - [ ] Apps are installed on instances
  - [ ] Tests execute successfully
  - [ ] Results are uploaded

### 6. Troubleshooting

If tests fail, check:

- [ ] GitHub Variables are set correctly (no typos in IPs)
- [ ] GitHub Secret password is correct
- [ ] SOAR instances are accessible from GitHub runners
  - Try: `curl -k https://<instance-ip>/rest/version` from a GitHub Action
- [ ] Service account has correct permissions
- [ ] Instances have enough resources to run tests

### 7. (Optional) Switch to CodeBuild

If you need to use CodeBuild runners instead of GitHub-hosted:

- [ ] Contact DevOps team to enable CodeBuild for SDK repo
- [ ] Follow instructions in `.github/workflows/RUNNER_CONFIGURATION.md`
- [ ] Update workflow to use CodeBuild runners
- [ ] Test the new configuration

---

## 📋 Quick Reference

### GitHub Variables (Public)
```
PHANTOM_INSTANCE_PREVIOUS_VERSION_IP = "10.x.x.x"
PHANTOM_INSTANCE_NEXT_OL8_VERSION_IP = "10.x.x.x"
PHANTOM_USERNAME = "admin"
NUM_TEST_RETRIES = "2"
```

### GitHub Secrets (Private)
```
PHANTOM_PASSWORD = "your-secure-password"
```

### Test Locally (Before CI)
```bash
# Export environment variables
export PHANTOM_URL="https://<instance-ip>"
export PHANTOM_USERNAME="admin"
export PHANTOM_PASSWORD="password"

# Build the apps
cd tests/example_app
uv run soarapps package build . --output-file /tmp/example_app.tgz

cd ../example_app_with_webhook
uv run soarapps package build . --output-file /tmp/example_app_with_webhook.tgz

# Install apps
python .github/utils/app_rest_installer.py /tmp/example_app.tgz <ip> admin password
python .github/utils/app_rest_installer.py /tmp/example_app_with_webhook.tgz <ip> admin password

# Run tests
cd ../..
uv run pytest tests/integration/ -v -m integration
```

---

## 🎉 You're Done!

Once all checkboxes are complete, your integration tests are ready!

The tests will automatically run on:
- Every push to `main`, `next`, or `beta` branches
- Every pull request

Results will be visible in the "Actions" tab of your repository.
