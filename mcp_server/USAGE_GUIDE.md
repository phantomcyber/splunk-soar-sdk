# MCP Server Usage Guide - All Test Types

The SOAR Test Assistant MCP server is **very powerful** and handles ALL types of tests:

---

## 🎯 What It Can Do

### 1. App Tests ✅
Fix tests for SOAR apps built with the SDK

### 2. SDK Unit Tests ✅
Fix the SDK's own unit tests

### 3. SDK Integration Tests ✅
Fix integration tests that run against live SOAR instances

---

## 📋 Usage Examples in Claude Code

### Scenario 1: Fix App Tests

**You ask Claude Code:**
```
"Run and fix tests for tests/example_app"
```

**What happens:**
1. MCP server detects it's an app (has `[tool.soar.app]` in pyproject.toml)
2. Runs: `soarapps app test tests/example_app`
3. Analyzes failures
4. Fixes (e.g., installs missing packages)
5. Re-runs until passing

**Example output:**
```
[app] Iteration 1/5...
  Detected: ModuleNotFoundError: No module named 'colorama'
  Fixing: Installing colorama...
  ✓ Fixed!

[app] Iteration 2/5...
  ✓ All tests passed!

Summary:
- Type: App Tests
- Iterations: 2
- Fixes: Installed colorama
- Result: SUCCESS
```

---

### Scenario 2: Fix SDK Unit Tests

**You ask Claude Code:**
```
"Fix failing SDK unit tests"
```

or more specifically:

```
"Run and fix tests at /path/to/splunk-soar-sdk"
```

**What happens:**
1. MCP server detects it's the SDK (has `src/soar_sdk/`)
2. Auto-detects test type: `sdk_unit`
3. Runs: `soarapps test unit`
4. Analyzes failures
5. Fixes (e.g., installs missing SDK dependencies)
6. Re-runs until passing

**Example output:**
```
[sdk_unit] Iteration 1/5...
Test Type: SDK Unit Tests
  Detected: ImportError: No module named 'toml'
  Fixing: Installing toml in SDK...
  ✓ Fixed!

[sdk_unit] Iteration 2/5...
  ✓ All SDK unit tests passed!

Summary:
- Type: SDK Unit Tests
- Iterations: 2
- Fixes: Added toml to SDK dependencies
- Result: SUCCESS
```

---

### Scenario 3: Fix SDK Integration Tests

**You ask Claude Code:**
```
"Run and fix SDK integration tests against 10.1.19.88
with username admin and password password"
```

**What happens:**
1. MCP server detects it's the SDK
2. Claude extracts SOAR instance credentials from your message
3. Sets test type: `sdk_integration`
4. Runs: `soarapps test integration 10.1.19.88`
5. Sets env vars: `PHANTOM_USERNAME=admin`, `PHANTOM_PASSWORD=password`
6. Analyzes failures (could be network, auth, SDK bugs, etc.)
7. Fixes what it can
8. Re-runs until passing

**Example output:**
```
[sdk_integration] Iteration 1/5...
Test Type: SDK Integration Tests
Instance: 10.1.19.88
  Running integration tests...
  FAILED: test_connectivity - HTTPStatusError: 401

  Analyzing: Authentication issue
  This could be:
  - Wrong credentials (user issue)
  - Missing auth header (SDK bug)

  Checking SDK auth code...
  Found: Missing Authorization header in phantom_instance.py
  Fixing: Adding auth header...
  ✓ Fixed SDK code!

[sdk_integration] Iteration 2/5...
  ✓ All integration tests passed!

Summary:
- Type: SDK Integration Tests
- Instance: 10.1.19.88
- Iterations: 2
- Fixes: Fixed authentication in phantom_instance.py
- Result: SUCCESS
```

---

## 🤖 Auto-Detection Logic

The MCP server automatically detects test type based on path:

```
Path Structure Detection:
├─ Has src/soar_sdk/ ?
│  ├─ Yes → It's the SDK
│  │  ├─ Has tests/integration/ ?
│  │  │  ├─ Yes → sdk_integration
│  │  │  └─ No → sdk_unit
│  └─ No → Check pyproject.toml
│     ├─ Has [tool.soar.app] ?
│     │  ├─ Yes → app
│     │  └─ No → app (default)
```

---

## 🎮 Advanced Usage

### Explicit Test Type

If auto-detection doesn't work, specify explicitly:

**In Claude Code:**
```
"Use run_and_fix_tests with path='/path/to/sdk'
and test_type='sdk_unit'"
```

### Specific Test Files

**In Claude Code:**
```
"Fix tests in tests/integration/test_example_app.py only"
```

MCP call will include:
```json
{
  "path": "/path/to/sdk",
  "test_type": "sdk_integration",
  "test_path": "tests/integration/test_example_app.py",
  "soar_instance": {"ip": "...", "username": "...", "password": "..."}
}
```

### Verbose Mode

**In Claude Code:**
```
"Fix SDK tests with verbose output"
```

Shows detailed iteration-by-iteration progress.

---

## 📊 Comparison Table

| Feature | App Tests | SDK Unit | SDK Integration |
|---------|-----------|----------|-----------------|
| **Command** | `soarapps app test` | `soarapps test unit` | `soarapps test integration` |
| **Needs SOAR** | ❌ No | ❌ No | ✅ Yes |
| **Speed** | Fast | Fast | Slow (network) |
| **Can Fix** | Dependencies, imports | Dependencies, imports, SDK code | Auth, network, SDK bugs |
| **Working Dir** | App dir | SDK root | SDK root |
| **Env Vars** | None | None | PHANTOM_* |

---

## 🔧 What Can Be Auto-Fixed?

### Currently Auto-Fixable ✅

1. **Import Errors (All test types)**
   - Missing Python packages
   - Fix: `uv add <package>`

2. **Dependency Issues (All test types)**
   - Outdated versions
   - Missing dependencies
   - Fix: Update pyproject.toml

### Requires Manual Review ⚠️

1. **Assertion Errors**
   - Test expectations wrong
   - Needs: Review test logic

2. **SDK Code Bugs**
   - Logic errors in SDK source
   - Needs: Code analysis + patch

3. **App Code Bugs**
   - Logic errors in app
   - Needs: Code analysis + patch

4. **Integration Issues**
   - Network problems
   - SOAR instance configuration
   - Needs: Infrastructure fixes

---

## 🎯 Real-World Scenarios

### Scenario: Developing a New App

**Day 1** - Initial tests failing:
```
You: "Fix tests for my new app at apps/my_slack_app"
MCP: [app] Installing missing dependencies... ✓
     All tests pass!
```

**Day 2** - Added new action, tests fail:
```
You: "Fix tests in apps/my_slack_app/tests/test_actions.py"
MCP: [app] Found ImportError for 'slack_sdk'
     Installing slack_sdk... ✓
     Re-running... All tests pass!
```

---

### Scenario: SDK Development

**Bug Report** - Users report auth issues:
```
You: "Run SDK integration tests against 10.1.19.88
     (admin/password)"
MCP: [sdk_integration] Test failed: 401 Unauthorized
     Analyzing SDK auth code...
     Found bug in phantom_instance.py
     Fixed: Added missing auth header ✓
     Re-running... All tests pass!
```

**Code Review** - Unit tests failing:
```
You: "Fix SDK unit tests"
MCP: [sdk_unit] Found: ImportError: No module named 'httpx'
     Installing httpx in SDK... ✓
     Re-running... All tests pass!
```

---

### Scenario: CI/CD Integration

While you can run the MCP server locally, you can also use it in automation:

```bash
# In CI/CD pipeline
# The MCP server can be called programmatically

# Example: Run and fix app tests in CI
uv run python -c "
from mcp_client import call_tool
result = call_tool('run_and_fix_tests', {
    'path': './my_app',
    'test_type': 'app',
    'max_iterations': 3
})
print(result)
"
```

---

## 🚨 Error Handling

### MCP Server Errors

**"Path does not exist"**
- Check the path you provided
- Use absolute paths or correct relative paths

**"Integration tests require soar_instance"**
- You need to provide SOAR instance details
- Format: `{"ip": "10.1.19.88", "username": "admin", "password": "pass"}`

**"Unknown test type"**
- Auto-detection failed
- Manually specify: `test_type='app'` or `'sdk_unit'` or `'sdk_integration'`

### Test Failures

**"No fixes available"**
- Issue is not auto-fixable
- Review the analysis for manual fix suggestions
- Might be assertion error, logic bug, etc.

**"Max iterations reached"**
- Tests still failing after 5 attempts
- Complex issues that need manual intervention
- Check the analysis for root cause

---

## 💡 Tips & Tricks

### Tip 1: Let It Auto-Detect
Don't specify test_type unless needed - auto-detection is smart!

### Tip 2: Use Verbose for Debugging
Add "with verbose output" to see detailed progress

### Tip 3: Start Small
Fix one test file at a time when debugging:
```
"Fix tests in tests/test_specific.py"
```

### Tip 4: Integration Tests Need Credentials
Always provide username and password for integration tests

### Tip 5: Check Analysis Even on Success
The analysis shows what was wrong, useful for understanding issues

---

## 🎓 Learning Mode

Want to understand what the MCP server is doing?

**Ask Claude Code:**
```
"Run and fix tests with verbose output,
and explain each step you're taking"
```

Claude will narrate the MCP server's actions:
- Test type detection
- Command execution
- Failure analysis
- Fix application
- Re-running logic

---

## 📞 Troubleshooting

### MCP Server Not Responding

1. Check it's running:
```bash
cd mcp_server
timeout 1 uv run soar_test_assistant
```

2. Restart Claude Code

3. Check config:
```bash
cat ~/.config/claude-code/mcp_settings.json
```

### Tests Still Failing After Fixes

1. Check what was attempted:
   - Look at the analysis
   - See what fixes were applied

2. Some issues need manual intervention:
   - Logic bugs
   - Assertion failures
   - Configuration issues

3. Try with verbose mode for more details

---

## 🚀 Summary

The MCP server is **VERY POWERFUL** because it:

✅ Works with ALL test types
✅ Auto-detects what you're testing
✅ Fixes common issues automatically
✅ Handles SDK unit tests
✅ Handles SDK integration tests
✅ Handles app tests
✅ Supports SOAR instance credentials
✅ Iterates until tests pass
✅ Provides detailed analysis

**Just tell Claude Code what you want to fix, and it handles the rest!**
