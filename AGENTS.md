# AGENTS.md

Repository-specific instructions for the Splunk SOAR SDK. Merge these rules with any applicable
workspace-level instructions.

## Tooling

- Use `uv` for dependency management and command execution. Do not introduce a parallel `pip` or
  virtualenv workflow.
- The supported Python versions are 3.13 and 3.14. Preserve compatibility with both.

## Testing

- The full unit test suite is cheap and normally takes less than 30 seconds. Run it with
  `uv run pytest -n auto` for every code or test change. Prefer the full suite over targeted
  tests because a narrowly scoped run can miss related failures. Targeted tests may help during
  iteration, but they do not replace the full-suite check.
- Maintain 100% unit-test coverage.
- When changing a default, test the omitted-value behavior and every supported explicit override.
  Do not rely only on schema or generated-output assertions.
- Diagnose integration failures separately from unit-test results. Lab connectivity can fail before
  the integration suite exercises SDK code.

## Compatibility And Generated Files

- Treat SDK models, defaults, generated metadata, templates, shims, and CLI behavior as public API.
  Clearly identify breaking changes and provide migration guidance.
- Keep source definitions and checked-in generated fixtures synchronized. Change the source first,
  then update the corresponding generated example app metadata.
- Example apps are also documentation inputs through Sphinx `literalinclude` directives. Avoid
  unrelated changes to them.

## Releases And Commits

- Use Conventional Commits.
- Do not bump versions manually; semantic-release owns versioning after merge.
- Every release-producing pull request must add exactly one `.changes/*.rst` fragment with one
  user-facing item beginning with `Feature:`, `Fix:`, or `Docs:`.
- For a breaking release, put `Breaking:` immediately after the fragment category and explain the
  user impact and migration step.
- Test-only, documentation-only, CI-only, and maintenance commits do not require release fragments.

## Scope

- Keep changes narrow. Avoid unrelated template, shim, generated-file, or formatting churn.
