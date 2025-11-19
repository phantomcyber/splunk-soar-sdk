# Quick Start - Testing SOAR Test Assistant

**TL;DR**: Run this one command and you're done:

```bash
./scripts/setup_local_test.sh
```

Then optionally:
```bash
./scripts/run_demo.sh
```

---

## What You Get

After running the setup script, you'll have:

1. ✅ **`soarapps app test`** - Test any SOAR app
2. ✅ **`soarapps test integration <ip>`** - Test against live SOAR instance
3. ✅ **MCP Server for Claude Code** - AI-powered auto-fix

---

## Quick Test (30 seconds)

```bash
# 1. Run setup
./scripts/setup_local_test.sh

# 2. Test it works
cd tests/example_app
soarapps app test

# Done! ✓
```

---

## Test Auto-Fix in Claude Code

1. **Restart Claude Code** (important!)
2. **Type this**:
   ```
   Run tests for tests/example_app and auto-fix any failures
   ```
3. **Watch the magic** ✨

---

## Test Integration (with SOAR instance)

```bash
export PHANTOM_USERNAME="soar_local_admin"
export PHANTOM_PASSWORD="password"
soarapps test integration 10.1.19.88
```

---

## Need More Details?

- **Full steps**: See `TESTING_AND_DEPLOYMENT_STEPS.md`
- **Script docs**: See `scripts/README.md`
- **MCP server**: See `mcp_server/README.md`

---

## Troubleshooting

### Setup script fails
```bash
# Check you have uv
which uv

# Check Python version
python3 --version  # Should be 3.13 or 3.14
```

### MCP server not in Claude Code
```bash
# Check config
cat ~/.config/claude-code/mcp_settings.json

# Restart Claude Code completely
```

### Tests fail
```bash
# Re-sync dependencies
cd tests/example_app
uv sync
```

---

## That's It!

You're ready to:
- ✅ Test SOAR apps
- ✅ Run integration tests
- ✅ Use AI auto-fix in Claude Code

Questions? Read the full docs in `TESTING_AND_DEPLOYMENT_STEPS.md`
