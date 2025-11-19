# SOAR Test Assistant - Quick Start Guide

This guide will help you get started with the SOAR Test Assistant MCP server for AI-powered test auto-fixing in Claude Code.

## What Does It Do?

The SOAR Test Assistant provides three powerful AI tools in Claude Code:

1. **`run_and_fix_tests`** - Automatically runs tests, analyzes failures, applies fixes, and re-runs until passing
2. **`analyze_test_failure`** - Analyzes pytest output to identify root causes (SDK vs app bugs)
3. **`fix_test_failure`** - Applies automated fixes based on analysis

## Installation

### Quick Install (Recommended)

```bash
cd /Users/grokas/dev/hackathon/splunk-soar-sdk/mcp_server
./install.sh
```

This script will:
- Install dependencies
- Configure the MCP server in Claude Code
- Back up your existing config

### Manual Install

1. Install dependencies:
```bash
cd /Users/grokas/dev/hackathon/splunk-soar-sdk/mcp_server
uv sync
```

2. Add to `~/.config/claude-code/mcp_settings.json`:
```json
{
  "mcpServers": {
    "soar-test-assistant": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/grokas/dev/hackathon/splunk-soar-sdk/mcp_server",
        "soar_test_assistant"
      ]
    }
  }
}
```

3. Restart Claude Code

## Usage Examples

### Example 1: Auto-fix failing tests

In Claude Code, simply ask:

```
Can you run tests for the example app at tests/example_app and auto-fix any failures?
```

Claude Code will use the `run_and_fix_tests` tool automatically.

### Example 2: Analyze specific test output

```
I have this pytest output: [paste output]
Can you analyze what's wrong?
```

Claude Code will use `analyze_test_failure` to provide insights.

### Example 3: Manual workflow

You can also request specific tool usage:

```
Use run_and_fix_tests on tests/example_app with max_iterations=10 and verbose=true
```

## How It Works

### Auto-Fix Flow

1. **Run Tests**: Executes `soarapps app test <app_path>`
2. **Analyze Failures**: Parses pytest output to identify:
   - Failed tests
   - Error types (ImportError, AssertionError, etc.)
   - SDK bugs vs app bugs
   - Root causes
3. **Apply Fixes**: Automatically fixes common issues:
   - Missing dependencies → `uv add <package>`
   - Import errors → Install packages
   - (More fix types coming soon)
4. **Re-run**: Repeats until tests pass or max iterations reached
5. **Report**: Provides summary of fixes applied

### What Can Be Auto-Fixed?

Currently auto-fixable:
- ✅ Missing Python packages (ImportError, ModuleNotFoundError)
- ✅ Simple dependency issues

Planned (requires manual review):
- ⚠️ Assertion errors
- ⚠️ Type errors
- ⚠️ Fixture errors

## Architecture

```
┌─────────────────┐
│  Claude Code    │
│   (User asks)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   MCP Server    │
│ (soar_test_     │
│  assistant)     │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│Analyzer│ │ Fixer │
└───────┘ └───────┘
    │         │
    └────┬────┘
         ▼
┌─────────────────┐
│ soarapps CLI    │
│  (app test)     │
└─────────────────┘
```

## Configuration

### Changing Max Iterations

Default is 5 iterations. To change:

```
run_and_fix_tests with max_iterations=10
```

### Verbose Output

Enable detailed output:

```
run_and_fix_tests with verbose=true
```

### Specific Test Path

Run only specific tests:

```
run_and_fix_tests on my_app with test_path="tests/test_actions.py"
```

## Troubleshooting

### MCP Server Not Found

1. Check installation:
```bash
cat ~/.config/claude-code/mcp_settings.json
```

2. Verify server starts:
```bash
cd /Users/grokas/dev/hackathon/splunk-soar-sdk/mcp_server
uv run soar_test_assistant
```

3. Restart Claude Code

### Tests Not Running

Ensure `soarapps` CLI is available:
```bash
soarapps --version
```

### No Fixes Applied

Some issues can't be auto-fixed yet. Check the analysis for manual fix suggestions.

## For Marketplace Publishing

This MCP server is designed to be published to the Anthropic MCP marketplace. To prepare:

1. Ensure all dependencies are pinned
2. Add marketplace metadata to `pyproject.toml`
3. Create comprehensive documentation
4. Add more auto-fix capabilities
5. Add tests for the MCP server itself

## Development

### Adding New Fix Types

Edit `src/soar_test_assistant/test_fixer.py` and add:

1. New `_fix_<type>_error` method
2. Register in `_apply_fix` method
3. Add corresponding analysis in `test_analyzer.py`

### Testing Locally

```bash
cd /Users/grokas/dev/hackathon/splunk-soar-sdk/mcp_server
uv run pytest
```

## Support

For issues or feature requests:
- SDK Issues: https://github.com/splunk/splunk-soar-sdk
- MCP Issues: Open an issue in this repository

## License

Part of the Splunk SOAR SDK - Copyright (c) Splunk Inc., 2025
