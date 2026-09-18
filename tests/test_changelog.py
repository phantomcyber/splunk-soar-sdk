"""Tests for the repository changelog fragment utility."""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / ".github/utils/changelog.py"
SCRIPT_SPEC = importlib.util.spec_from_file_location("changelog", SCRIPT_PATH)
assert SCRIPT_SPEC is not None
assert SCRIPT_SPEC.loader is not None
changelog = importlib.util.module_from_spec(SCRIPT_SPEC)
sys.modules["changelog"] = changelog
SCRIPT_SPEC.loader.exec_module(changelog)


def write_changelog(path: Path) -> None:
    """Write a minimal changelog with two major-version groups."""

    path.write_text(
        """Changelog
=========

.. dropdown:: SDK 4
   :open:

   .. rubric:: 4.4.2 (2026-09-15)

   * Fix: Existing behavior.

.. dropdown:: SDK 3

   .. rubric:: 3.29.0 (2026-08-11)

   * Feature: Older behavior.
""",
        encoding="utf-8",
    )


def test_validate_fragment_accepts_prefixed_multiline_item(tmp_path: Path) -> None:
    """Accept a categorized item and its indented continuation."""

    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    fragment_path = fragments_path / "asset-fields.rst"
    fragment_path.write_text(
        "* Feature: Add support for ``AssetField`` uploads.\n"
        "  The field now accepts a file path.\n",
        encoding="utf-8",
    )

    changes = changelog.validate_fragments(fragments_path)

    assert len(changes) == 1
    assert changes[0].category == "Feature"
    assert not changes[0].breaking


def test_validate_fragment_rejects_unapproved_category(tmp_path: Path) -> None:
    """Reject internal commit categories in user-facing fragments."""

    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    (fragments_path / "internal.rst").write_text(
        "* Chore: Refresh tooling.\n",
        encoding="utf-8",
    )

    with pytest.raises(changelog.ChangelogError, match="each entry must start"):
        changelog.validate_fragments(fragments_path)


def test_validate_fragment_rejects_multiple_items(tmp_path: Path) -> None:
    """Keep one PR fragment focused on one changelog item."""

    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    (fragments_path / "too-many.rst").write_text(
        "* Feature: Add one thing.\n\n* Fix: Correct another thing.\n",
        encoding="utf-8",
    )

    with pytest.raises(changelog.ChangelogError, match="exactly one entry"):
        changelog.validate_fragments(fragments_path)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("fix(docs): correct the rendered changelog\n", "patch"),
        ("feat(api): add a client method\n", "minor"),
        ("feat!: rename the client method\n", "major"),
        (
            "fix(api): change the client method\n\n"
            "BREAKING CHANGE: migrate callers to the new method.\n",
            "major",
        ),
        ('Revert "feat(api): add a client method"\n', "patch"),
        ("docs: correct the rendered changelog\n", None),
        ("chore(release): update version to 5.0.1 [skip ci]\n", None),
    ],
)
def test_release_type_for_commit(message: str, expected: str | None) -> None:
    """Mirror semantic-release's release-producing commit categories."""

    assert changelog.release_type_for_commit(message) == expected


def test_validate_commit_requires_indexed_fragment(tmp_path: Path) -> None:
    """Require release-producing commits to stage pending changelog language."""

    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()

    with pytest.raises(changelog.ChangelogError, match="stage a pending"):
        changelog.validate_commit_message(
            "fix(api): prevent an SDK error\n",
            fragments_path=fragments_path,
            indexed_fragment_paths=[],
        )


def test_validate_commit_accepts_pending_fragment(tmp_path: Path) -> None:
    """Accept a release-producing commit with a valid indexed fragment."""

    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    fragment_path = fragments_path / "release-item.rst"
    fragment_path.write_text("* Fix: Prevent an SDK error.\n", encoding="utf-8")

    changes = changelog.validate_commit_message(
        "fix(api): prevent an SDK error\n",
        fragments_path=fragments_path,
        indexed_fragment_paths=[fragment_path],
    )

    assert len(changes) == 1


def test_validate_commit_requires_breaking_language(tmp_path: Path) -> None:
    """Require migration guidance for a breaking release commit."""

    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    fragment_path = fragments_path / "release-item.rst"
    fragment_path.write_text("* Feature: Add a replacement API.\n", encoding="utf-8")

    with pytest.raises(changelog.ChangelogError, match="begins with 'Breaking:'"):
        changelog.validate_commit_message(
            "feat!: replace the API\n",
            fragments_path=fragments_path,
            indexed_fragment_paths=[fragment_path],
        )


def test_validate_commit_ignores_non_release_commit(tmp_path: Path) -> None:
    """Do not require changelog language for commits semantic-release ignores."""

    changes = changelog.validate_commit_message(
        "chore(ci): refresh workflow tooling\n",
        fragments_path=tmp_path / ".changes",
        indexed_fragment_paths=[],
    )

    assert changes == []


def test_render_consumes_fragments_in_existing_major_group(tmp_path: Path) -> None:
    """Insert a stable release before existing entries and consume its fragment."""

    changelog_path = tmp_path / "changelog.rst"
    write_changelog(changelog_path)
    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    fragment_path = fragments_path / "new-feature.rst"
    fragment_path.write_text("* Feature: Add a new SDK feature.\n", encoding="utf-8")

    count = changelog.render_changelog(
        version="4.4.3",
        release_date="2026-09-16",
        changelog_path=changelog_path,
        fragments_path=fragments_path,
    )

    rendered = changelog_path.read_text(encoding="utf-8")
    assert count == 1
    assert not fragment_path.exists()
    assert rendered.index("4.4.3") < rendered.index("4.4.2")
    assert "   * Feature: Add a new SDK feature." in rendered
    assert rendered.count("   :open:") == 1


def test_release_notes_use_pending_fragment_language(tmp_path: Path) -> None:
    """Return fragment prose for semantic-release without consuming it."""

    changelog_path = tmp_path / "changelog.rst"
    write_changelog(changelog_path)
    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    fragment_path = fragments_path / "release-item.rst"
    fragment_path.write_text("* Fix: Prevent an SDK error.\n", encoding="utf-8")

    notes = changelog.release_notes(
        version="4.4.3",
        changelog_path=changelog_path,
        fragments_path=fragments_path,
    )

    assert notes == "* Fix: Prevent an SDK error."
    assert fragment_path.exists()


def test_render_handles_the_backfilled_changelog(tmp_path: Path) -> None:
    """Render a future patch release into the repository's full changelog shape."""

    changelog_path = tmp_path / "changelog.rst"
    shutil.copyfile(SCRIPT_PATH.parents[2] / "docs/changelog.rst", changelog_path)
    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    fragment_path = fragments_path / "future-fix.rst"
    fragment_path.write_text("* Fix: Prevent a future SDK error.\n", encoding="utf-8")

    changelog.render_changelog(
        version="5.0.1",
        release_date="2026-09-16",
        changelog_path=changelog_path,
        fragments_path=fragments_path,
    )

    rendered = changelog_path.read_text(encoding="utf-8")
    assert rendered.index("5.0.1") < rendered.index("5.0.0")
    assert rendered.count(".. dropdown:: SDK") == 5
    assert rendered.count("   :open:") == 1
    assert not fragment_path.exists()


def test_validate_pull_request_requires_one_current_fragment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validate the fragment changed by a release-producing pull request."""

    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    fragment_path = fragments_path / "release-item.rst"
    fragment_path.write_text("* Fix: Prevent an SDK error.\n", encoding="utf-8")
    changelog_path = tmp_path / "changelog.rst"
    write_changelog(changelog_path)
    monkeypatch.setattr(
        changelog,
        "_changed_fragment_paths",
        lambda _base, _head: [fragment_path],
    )

    changes = changelog.validate_for_pull_request(
        "base",
        "head",
        version="4.4.3",
        fragments_path=fragments_path,
        changelog_path=changelog_path,
    )

    assert len(changes) == 1
    assert changes[0].category == "Fix"


def test_validate_no_release_rejects_new_fragment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent a non-release pull request from leaving a future fragment behind."""

    fragment_path = tmp_path / ".changes" / "unreleased.rst"
    fragment_path.parent.mkdir()
    fragment_path.write_text(
        "* Docs: Explain the release workflow.\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        changelog,
        "_changed_fragment_paths",
        lambda _base, _head: [fragment_path],
    )

    with pytest.raises(changelog.ChangelogError, match="without a release"):
        changelog.validate_no_pull_request_fragment("base", "head")


def test_render_starts_new_major_with_breaking_callout(tmp_path: Path) -> None:
    """Create a new open major group when a marked breaking item is present."""

    changelog_path = tmp_path / "changelog.rst"
    write_changelog(changelog_path)
    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    fragment_path = fragments_path / "breaking-change.rst"
    fragment_path.write_text(
        "* Feature: Breaking: Rename the client method and migrate callers.\n",
        encoding="utf-8",
    )

    changelog.render_changelog(
        version="5.0.0",
        release_date="2026-09-17",
        changelog_path=changelog_path,
        fragments_path=fragments_path,
    )

    rendered = changelog_path.read_text(encoding="utf-8")
    assert rendered.index("SDK 5") < rendered.index("SDK 4")
    assert "   **Breaking changes:**" in rendered
    assert "   * Feature: Breaking: Rename the client method" in rendered
    assert rendered.count("   :open:") == 1


def test_render_rejects_unmarked_new_major(tmp_path: Path) -> None:
    """Require explicit migration language for a new major line."""

    changelog_path = tmp_path / "changelog.rst"
    write_changelog(changelog_path)
    fragments_path = tmp_path / ".changes"
    fragments_path.mkdir()
    (fragments_path / "missing-migration.rst").write_text(
        "* Feature: Add a new API.\n",
        encoding="utf-8",
    )

    with pytest.raises(changelog.ChangelogError, match="must begin with 'Breaking:'"):
        changelog.render_changelog(
            version="5.0.0",
            release_date="2026-09-17",
            changelog_path=changelog_path,
            fragments_path=fragments_path,
        )


def test_render_requires_pending_fragments(tmp_path: Path) -> None:
    """Fail a stable release when no PR language is available."""

    changelog_path = tmp_path / "changelog.rst"
    write_changelog(changelog_path)

    with pytest.raises(changelog.ChangelogError, match="no pending"):
        changelog.render_changelog(
            version="4.4.3",
            release_date="2026-09-16",
            changelog_path=changelog_path,
            fragments_path=tmp_path / ".changes",
        )
