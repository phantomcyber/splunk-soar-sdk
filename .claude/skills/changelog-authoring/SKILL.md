---
name: changelog-authoring
description: "Use when adding one version-independent user-facing SDK changelog fragment for a pull request. CI supplies the release version and date; do not use this skill for historical all-release backfills."
---

# Changelog Authoring

> This repository-local skill was authored by Codex.

Use this skill to author one user-facing SDK changelog fragment for a pull
request. The fragment supplies the language; CI supplies the eventual release
version and date. Do not edit the assembled changelog during normal feature
work.

## Repository conventions

- Add one fragment at ``.changes/<short-slug>.rst``. Keep one user-facing item
  in the fragment; use another invocation for another item.
- Start the item with exactly one of ``* Fix:``, ``* Feature:``, or ``* Docs:``.
  Use ``Breaking:`` immediately after the category when the item requires a
  migration, for example ``* Feature: Breaking: Rename ...``.
- Write concise active prose for SDK users. Use RST inline literals for APIs,
  commands, identifiers, and version numbers. Explain the user impact and
  migration step for breaking changes. Do not include a release version, date,
  commit hash, author, ticket number, or internal-only implementation detail.
- Do not add a version heading, date, ``git_changelog`` directive, or
  authorship attestation to a fragment or to ``docs/changelog.rst``.
- The release renderer combines all pending fragments into one release entry,
  adds the CI-provided version/date, places it in the appropriate
  ``.. dropdown:: SDK N`` group, and removes consumed fragments. Alpha and beta
  releases retain fragments until the stable release on ``main``.
- The historical coverage helper in
  ``scripts/check-release-coverage.sh`` is for explicit backfill or audit work
  only. Do not run it or expand the task to all releases during normal entry
  maintenance.
- ``sphinx-git`` and the generated directive are retired. Do not add them
  back.

## Workflow

1. Inspect ``git status --short`` and the existing fragments. Preserve
   unrelated changes.
2. Inspect the relevant diff and commit subjects. Use ``feat``/``fix``/``docs``
   as category evidence, but rewrite the result as user-facing prose. Omit
   merge commits, release bookkeeping, tests, CI, formatting, and dependency
   churn unless they change user-visible behavior, compatibility, security, or
   installation.
3. Create exactly one new ``.changes/<short-slug>.rst`` file containing one
   prefixed item. Do not guess or reserve the eventual version number.
4. If the change is breaking, put ``Breaking:`` after the category and state
   who is affected plus the concrete migration. A new-major release cannot be
   rendered without at least one such item.
Keep edits limited to the one fragment and explicitly requested supporting
files. Do not create tags, commits, merge requests, or external comments.

## Validation

Validate the single fragment:

       python3 .github/utils/changelog.py validate
       git diff --check
       uv run pre-commit run codespell --files .changes/<short-slug>.rst

The final docs build belongs to CI after semantic-release renders the entry.
Use the historical coverage helper only for an explicit backfill or
coverage-audit request:

       .claude/skills/changelog-authoring/scripts/check-release-coverage.sh \
         docs/changelog.rst 1.0.0

When reporting completion, name the fragment created, its category, and the
validation results. Attribute authored prose to Codex in accordance with
repository instructions.
