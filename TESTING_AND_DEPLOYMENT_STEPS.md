# Testing and Deployment Steps for SOAR Test Assistant

This document provides step-by-step instructions for testing and deploying the SOAR Test Assistant MCP server.

---

## Table of Contents

1. [Quick Local Testing](#quick-local-testing)
2. [Manual Testing Steps](#manual-testing-steps)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Deployment to Marketplace](#deployment-to-marketplace)
5. [Post-Deployment](#post-deployment)

---

## Quick Local Testing

### Automated Setup (Easiest)

```bash
# Run the automated setup script
cd /Users/grokas/dev/hackathon/splunk-soar-sdk
./scripts/setup_local_test.sh
```

This will:
- ✅ Install all dependencies
- ✅ Configure the MCP server
- ✅ Create test scenarios
- ✅ Verify everything works

### Run the Demo

```bash
./scripts/run_demo.sh
```

This demonstrates:
1. Running app tests
2. Auto-fixing failures
3. Integration tests

---

## Manual Testing Steps

### Step 1: Test the App Test Command

#### 1.1 Basic Test
```bash
cd tests/example_app
soarapps app test
```

**Expected**: Tests run and pass

#### 1.2 Specific Test File
```bash
soarapps app test -t tests/test_example.py
```

**Expected**: Only specified tests run

#### 1.3 With Coverage
```bash
soarapps app test --coverage
```

**Expected**: Coverage report shown

#### 1.4 Watch Mode
```bash
soarapps app test --watch
```

**Expected**: Tests re-run on file changes (Ctrl+C to exit)

---

### Step 2: Test Integration Tests

#### 2.1 Set Credentials
```bash
export PHANTOM_USERNAME="soar_local_admin"
export PHANTOM_PASSWORD="password"
```

#### 2.2 Run Against SOAR Instance
```bash
soarapps test integration 10.1.19.88
```

**Expected**: All integration tests pass

#### 2.3 Verbose Output
```bash
soarapps test integration 10.1.19.88 --verbose
```

**Expected**: Detailed test output shown

#### 2.4 Specific Tests
```bash
soarapps test integration 10.1.19.88 -t tests/integration/test_example_app.py
```

**Expected**: Only example_app tests run

---

### Step 3: Test MCP Server Auto-Fix

#### 3.1 Install MCP Server
```bash
cd mcp_server
./install.sh
```

**Expected**:
```
✓ Installation complete!
The SOAR Test Assistant MCP server is now installed and configured.
```

#### 3.2 Verify Installation
```bash
cat ~/.config/claude-code/mcp_settings.json
```

**Expected**: Should contain `soar-test-assistant` configuration

#### 3.3 Test Server Startup
```bash
cd mcp_server
timeout 1 uv run soar_test_assistant || echo "Server starts OK"
```

**Expected**: Server starts without errors (timeout is normal)

#### 3.4 Restart Claude Code
```bash
# Close and reopen Claude Code
```

#### 3.5 Test Auto-Fix in Claude Code

**In Claude Code, type:**
```
Can you check if the soar-test-assistant MCP server is available?
```

**Expected**: Claude Code confirms the server is available

**Then type:**
```
Run tests for tests/example_app and auto-fix any failures
```

**Expected**: Claude Code uses the MCP tools to run and fix tests

---

### Step 4: Test Auto-Fix Logic Manually

#### 4.1 Create a Failing Test
```bash
cd tests/example_app
cat > tests/test_auto_fix_demo.py << 'EOF'
def test_missing_library():
    import colorama  # Not installed
    assert colorama is not None
EOF
```

#### 4.2 Run Test (Should Fail)
```bash
soarapps app test -t tests/test_auto_fix_demo.py
```

**Expected**: Test fails with `ModuleNotFoundError: No module named 'colorama'`

#### 4.3 Use Claude Code to Fix
**In Claude Code:**
```
Run tests for tests/example_app/tests/test_auto_fix_demo.py and auto-fix failures
```

**Expected**:
1. Claude detects missing module
2. Runs `uv add colorama`
3. Re-runs tests
4. Tests pass

#### 4.4 Verify Fix
```bash
soarapps app test -t tests/test_auto_fix_demo.py
```

**Expected**: Tests now pass

---

## Pre-Deployment Checklist

### Code Quality

- [ ] **Remove hardcoded paths**
  ```bash
  grep -r "/Users/grokas" mcp_server/
  # Should return no results
  ```

- [ ] **Run linters**
  ```bash
  cd mcp_server
  uv run ruff check .
  uv run ruff format .
  ```

- [ ] **Type checking**
  ```bash
  uv run mypy src/
  ```

- [ ] **Run tests**
  ```bash
  uv run pytest
  ```

### Documentation

- [ ] **README is complete**
  ```bash
  # Check mcp_server/README.md has:
  # - Installation instructions
  # - Usage examples
  # - Troubleshooting
  ```

- [ ] **QUICKSTART guide exists**
  ```bash
  cat mcp_server/QUICKSTART.md
  ```

- [ ] **Examples are tested**
  ```bash
  # Verify all code examples in docs actually work
  ```

### Security

- [ ] **No secrets in code**
  ```bash
  grep -r "password\|token\|secret" mcp_server/src/
  # Review any matches
  ```

- [ ] **Dependencies are secure**
  ```bash
  uv run pip-audit
  ```

### Testing

- [ ] **Fresh install test**
  ```bash
  # In a new terminal/environment
  cd /tmp/test-install
  git clone <your-repo>
  cd <repo>/mcp_server
  ./install.sh
  # Should work without errors
  ```

- [ ] **Test on different Python versions**
  ```bash
  # Test with Python 3.13 and 3.14
  ```

- [ ] **Test all MCP tools**
  - [ ] `run_and_fix_tests`
  - [ ] `analyze_test_failure`
  - [ ] `fix_test_failure`

---

## Deployment to Marketplace

### Option 1: PyPI + MCP Marketplace (Recommended)

#### Step 1: Prepare Package

```bash
cd mcp_server

# Update version in pyproject.toml
# Ensure all metadata is correct
```

#### Step 2: Build Package

```bash
uv build
```

**Expected**: Creates `dist/soar_test_assistant-0.1.0.tar.gz`

#### Step 3: Test Package Locally

```bash
# In a test environment
uv tool install dist/soar_test_assistant-0.1.0.tar.gz
```

#### Step 4: Publish to Test PyPI

```bash
uv run twine upload --repository testpypi dist/*
```

#### Step 5: Test from Test PyPI

```bash
uv tool install --index-url https://test.pypi.org/simple/ soar-test-assistant
```

#### Step 6: Publish to PyPI

```bash
uv run twine upload dist/*
```

#### Step 7: Create GitHub Release

```bash
# On GitHub:
# 1. Go to Releases
# 2. Create new release
# 3. Tag: v0.1.0
# 4. Upload dist files
# 5. Add changelog
```

#### Step 8: Submit to MCP Marketplace

1. **Fork**: https://github.com/modelcontextprotocol/servers
2. **Add entry** to `servers.yaml`:
   ```yaml
   - name: soar-test-assistant
     description: AI-powered test analysis and auto-fixing for Splunk SOAR SDK
     author: Splunk Inc.
     sourceUrl: https://github.com/splunk/soar-test-assistant
     installCommand: uvx soar-test-assistant
   ```
3. **Create PR** with title: "Add SOAR Test Assistant MCP Server"
4. **Wait for review**

---

### Option 2: GitHub-Only Distribution

#### Step 1: Create Public Repo

```bash
# Create repo on GitHub: splunk/soar-test-assistant
```

#### Step 2: Push Code

```bash
cd mcp_server
git init
git add .
git commit -m "Initial release v0.1.0"
git remote add origin https://github.com/splunk/soar-test-assistant.git
git push -u origin main
git tag v0.1.0
git push --tags
```

#### Step 3: Update Installation Docs

Users can install with:
```bash
uvx --from git+https://github.com/splunk/soar-test-assistant soar_test_assistant
```

---

### Option 3: Splunk Internal Distribution

#### Step 1: Package for Internal Use

```bash
cd mcp_server
tar -czf soar-test-assistant-0.1.0.tar.gz .
```

#### Step 2: Upload to Internal Registry

```bash
# Follow Splunk internal procedures
```

#### Step 3: Document Internal Installation

```bash
# Instructions for Splunk employees
uv tool install --index-url https://internal.splunk.net/pypi soar-test-assistant
```

---

## Post-Deployment

### Monitor Usage

#### Check Downloads
```bash
# For PyPI
curl https://pypistats.org/api/packages/soar-test-assistant/recent
```

#### Check GitHub Stars
```bash
# Monitor: https://github.com/splunk/soar-test-assistant
```

### Handle Issues

#### Set up issue templates
```bash
# .github/ISSUE_TEMPLATE/bug_report.md
# .github/ISSUE_TEMPLATE/feature_request.md
```

#### Monitor issues
```bash
# Regularly check: https://github.com/splunk/soar-test-assistant/issues
```

### Release Updates

#### Version bump checklist
- [ ] Update version in `pyproject.toml`
- [ ] Update CHANGELOG.md
- [ ] Run all tests
- [ ] Build package
- [ ] Test installation
- [ ] Publish to PyPI
- [ ] Create GitHub release
- [ ] Announce in community

---

## Troubleshooting Common Issues

### MCP Server Not Found

**Symptom**: Claude Code doesn't show the tools

**Fix**:
```bash
# Check config
cat ~/.config/claude-code/mcp_settings.json

# Verify server runs
cd mcp_server
uv run soar_test_assistant

# Restart Claude Code completely
```

### soarapps Command Not Found

**Symptom**: MCP tools fail with "soarapps not found"

**Fix**:
```bash
# Install SDK
cd /path/to/splunk-soar-sdk
uv sync

# Verify
soarapps --version
```

### Tests Still Fail After Auto-Fix

**Symptom**: Auto-fix runs but tests still fail

**Check**:
1. Was the fix actually applied?
   ```bash
   git diff pyproject.toml
   ```
2. Were dependencies synced?
   ```bash
   cd your_app
   uv sync
   ```
3. Is the issue auto-fixable?
   - Currently only import errors are auto-fixed
   - Other errors need manual intervention

### Integration Tests Timeout

**Symptom**: Tests hang or timeout

**Fix**:
```bash
# Check SOAR instance is accessible
ping 10.1.19.88

# Verify credentials
curl -k -u soar_local_admin:password https://10.1.19.88/rest/version

# Check firewall/network
```

---

## Support and Resources

### Documentation
- SDK Docs: https://docs.splunk.com/Documentation/SOAR
- MCP Protocol: https://modelcontextprotocol.io/

### Community
- GitHub Issues: https://github.com/splunk/soar-test-assistant/issues
- Splunk Community: https://community.splunk.com/

### Internal
- Splunk Slack: #soar-sdk
- Email: soar-sdk@splunk.com

---

## Quick Reference

### Common Commands

```bash
# Test app locally
soarapps app test

# Test against SOAR instance
soarapps test integration <ip> -u <user> -p <pass>

# Install MCP server
cd mcp_server && ./install.sh

# Build package
cd mcp_server && uv build

# Publish to PyPI
cd mcp_server && uv run twine upload dist/*
```

### File Locations

```
SOAR SDK Root/
├── src/soar_sdk/cli/
│   ├── app/cli.py          # App test command
│   └── test/cli.py         # Integration test command
├── mcp_server/
│   ├── src/soar_test_assistant/
│   │   ├── server.py       # MCP server
│   │   ├── test_analyzer.py
│   │   └── test_fixer.py
│   ├── install.sh          # Installation script
│   └── README.md           # Documentation
├── scripts/
│   ├── setup_local_test.sh # Automated setup
│   └── run_demo.sh         # Demo runner
└── TESTING_AND_DEPLOYMENT_STEPS.md  # This file
```

---

## Next Steps

1. ✅ Run automated setup: `./scripts/setup_local_test.sh`
2. ✅ Test manually following Step 1-4
3. ✅ Complete pre-deployment checklist
4. ✅ Choose deployment option
5. ✅ Deploy and announce
6. ✅ Monitor and maintain

Good luck! 🚀
