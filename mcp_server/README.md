# SOAR Test Assistant MCP Server

An MCP server that provides automated test analysis and remediation capabilities for the SOAR SDK. This server orchestrates test execution, applies targeted fixes, and validates changes through an iterative workflow.

## Workflow

The server implements a two-phase analysis and remediation cycle:

### 1. analyze_tests - Test Execution and Failure Analysis
Executes the test suite and captures comprehensive diagnostic output including stack traces, assertion failures, and error context.

### 2. fix_and_run_tests - Automated Remediation and Validation
Applies proposed changes to source files, test fixtures, or dependencies, then re-executes the test suite to verify the fix.

The cycle repeats until all tests pass or unresolvable failures are identified.

## Tools

### `analyze_tests`

Executes the SDK test suite and returns detailed diagnostic output for failure analysis.

**Parameters:**
- `test_type`: `"unit"` or `"integration"` (default: `"unit"`)
- `test_path`: Optional specific test file/directory
- `soar_instance`: Required for integration tests: `{"ip": "...", "username": "...", "password": "..."}`

**Returns:**
- `status`: `"success"` or `"failed"`
- `test_output`: Complete pytest output with stack traces and context
- `message`: Diagnostic guidance for common failure patterns

**Example:**
```json
{
  "test_type": "unit",
  "test_path": "tests/cli/manifests/test_processors.py"
}
```

### `fix_and_run_tests`

Applies a set of proposed changes (file edits, command executions) and re-runs the test suite to validate the remediation.

**Parameters:**
- `test_type`: `"unit"` or `"integration"` (default: `"unit"`)
- `test_path`: Optional specific test file/directory
- `soar_instance`: Required for integration tests
- `changes`: Array of changes to apply

**Change Types:**

#### edit_file
Replace exact content in a file:
```json
{
  "type": "edit_file",
  "file": "tests/example_app/app.json",
  "old_content": "\"version\": \"1.0\"",
  "new_content": "\"version\": \"1.1\"",
  "reasoning": "Update version to match new release"
}
```

#### run_command
Execute a bash command:
```json
{
  "type": "run_command",
  "command": "cd tests/example_app && uv run python -c \"<regenerate fixture code>\"",
  "reasoning": "Regenerate outdated test fixture"
}
```

**Returns:**
- `status`: `"success"`, `"still_failing"`, or `"error"`
- `applied_changes`: List of changes that were applied
- `test_output`: New test results
- `errors`: Any errors encountered

## Example Session

Automated remediation workflow for a failing manifest processor test:

1. **Initial Analysis**: `analyze_tests` executes test suite
   - Detects assertion failure: `app_meta != expected_meta`
   - Identifies drift in test fixture `tests/example_app/app.json`

2. **Remediation Strategy**: Regenerate test fixture to match current processor output
   - Command: Invoke `ManifestProcessor` to generate updated manifest
   - Preserve existing `utctime_updated` field to maintain test stability

3. **Apply and Validate**: `fix_and_run_tests` executes regeneration command
   - Fixture updated with current expected values
   - Test suite re-executed
   - Returns `status: "success"`

## Installation

Run the installation script from the repository root:

```bash
./install
```

Or configure manually by adding to your MCP settings (`~/.config/claude-code/mcp_settings.json`):

```json
{
  "mcpServers": {
    "soar-test-assistant": {
      "command": "uv",
      "args": ["run", "soar-test-assistant"],
      "cwd": "/path/to/your/splunk-soar-sdk/mcp_server"
    }
  }
}
```

Then restart Claude Code.

## SDK-Only Focus

This MCP server is **exclusively for SOAR SDK tests**:
- **Unit tests**: `tests/` (excluding integration)
- **Integration tests**: `tests/integration/`

All tests run from the SDK root directory, which is auto-detected.

## Development

```bash
# Test the MCP server
uv run pytest
```
