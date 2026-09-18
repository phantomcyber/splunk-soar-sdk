#!/usr/bin/env python3
"""Validate and render version-independent SDK changelog fragments."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_PATH = ROOT / "docs/changelog.rst"
FRAGMENTS_PATH = ROOT / ".changes"

CATEGORIES = ("Fix", "Feature", "Docs")
CATEGORY_PATTERN = "|".join(CATEGORIES)
ENTRY_PATTERN = re.compile(
    rf"^\* (?P<category>{CATEGORY_PATTERN}): (?P<text>\S.*)$",
)
RELEASE_TYPES = {
    "feat": "minor",
    "fix": "patch",
    "perf": "patch",
    "revert": "patch",
}
COMMIT_HEADER_PATTERN = re.compile(
    r"^(?P<type>[A-Za-z][A-Za-z0-9-]*)"
    r"(?:\((?P<scope>[^()\r\n]+)\))?"
    r"(?P<breaking>!)?: (?P<description>\S.*)$",
)
BREAKING_FOOTER_PATTERN = re.compile(
    r"(?m)^[ \t]*BREAKING(?: CHANGE|-CHANGE):[ \t]*\S.*$",
)
REVERT_HEADER_PATTERN = re.compile(r'^Revert ".+"$')
FRAGMENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.rst$")
VERSION_PATTERN = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?P<suffix>[-+][0-9A-Za-z.-]+)?$",
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DROPDOWN_PATTERN = re.compile(r"^\.\. dropdown:: SDK (?P<major>\d+)$")
RUBRIC_PATTERN = re.compile(
    r"^\s*\.\. rubric:: (?P<version>\d+\.\d+\.\d+) "
    r"\((?P<date>\d{4}-\d{2}-\d{2})\)$",
)


class ChangelogError(ValueError):
    """Raised when a changelog fragment or document is invalid."""


@dataclass(frozen=True)
class Change:
    """One user-facing changelog item."""

    source: Path
    lines: tuple[str, ...]
    category: str
    breaking: bool


def _error(path: Path, line_number: int, message: str) -> ChangelogError:
    """Build a location-aware validation error."""

    return ChangelogError(f"{_display_path(path)}:{line_number}: {message}")


def _display_path(path: Path) -> Path:
    """Return a concise path when it belongs to the repository."""

    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def _parse_fragment(path: Path) -> list[Change]:
    """Parse one fragment and return its user-facing entries."""

    if not FRAGMENT_NAME_PATTERN.fullmatch(path.name):
        raise ChangelogError(
            f"{_display_path(path)}: filename must contain only letters, "
            "digits, dots, underscores, or hyphens",
        )

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ChangelogError(f"{_display_path(path)}: fragment is empty")

    entries: list[Change] = []
    current_lines: list[str] | None = None
    current_category = ""
    current_breaking = False

    def finish_entry() -> None:
        if current_lines is not None:
            entries.append(
                Change(
                    source=path,
                    lines=tuple(current_lines),
                    category=current_category,
                    breaking=current_breaking,
                ),
            )

    for line_number, line in enumerate(content.splitlines(), start=1):
        if line.rstrip() != line:
            raise _error(path, line_number, "trailing whitespace is not allowed")

        if not line.strip():
            continue

        match = ENTRY_PATTERN.fullmatch(line)
        if match:
            finish_entry()
            current_lines = [line]
            current_category = match.group("category")
            current_breaking = match.group("text").startswith("Breaking:")
            continue

        if current_lines is None:
            raise _error(
                path,
                line_number,
                "each entry must start with '* Fix:', '* Feature:', or '* Docs:'",
            )

        if not line.startswith("  "):
            raise _error(
                path,
                line_number,
                "continuation lines must be indented by at least two spaces",
            )

        stripped_line = line.lstrip()
        if stripped_line.startswith(("* ", "- ", ".. ")):
            raise _error(
                path,
                line_number,
                "nested bullets and reStructuredText directives are not allowed",
            )
        current_lines.append(line)

    finish_entry()
    if not entries:
        raise ChangelogError(f"{_display_path(path)}: fragment has no entries")
    if len(entries) != 1:
        raise ChangelogError(
            f"{_display_path(path)}: fragment must contain exactly one entry",
        )
    return entries


def fragment_paths(fragments_path: Path = FRAGMENTS_PATH) -> list[Path]:
    """Return all top-level fragment files in deterministic order."""

    if not fragments_path.is_dir():
        return []
    return sorted(path for path in fragments_path.glob("*.rst") if path.is_file())


def validate_fragments(fragments_path: Path = FRAGMENTS_PATH) -> list[Change]:
    """Validate all fragments and return their entries."""

    changes: list[Change] = []
    for path in fragment_paths(fragments_path):
        changes.extend(_parse_fragment(path))
    return changes


def release_type_for_commit(message: str) -> str | None:
    """Return the semantic-release level for a Conventional Commit message."""

    lines = [line for line in message.splitlines() if not line.startswith("#")]
    header = next((line for line in lines if line.strip()), "")
    if REVERT_HEADER_PATTERN.fullmatch(header):
        return "patch"

    match = COMMIT_HEADER_PATTERN.fullmatch(header)
    if match is None:
        return None
    if match.group("breaking") or BREAKING_FOOTER_PATTERN.search("\n".join(lines)):
        return "major"
    return RELEASE_TYPES.get(match.group("type").lower())


def _indexed_fragment_paths() -> list[Path]:
    """Return pending fragments present in the Git index."""

    git_path = shutil.which("git")
    if git_path is None:
        raise ChangelogError("git is required to validate commit changelog coverage")
    result = subprocess.run(  # noqa: S603
        [git_path, "ls-files", "--cached", "--full-name", "--", ".changes"],
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
    )
    return sorted(
        ROOT / item
        for item in result.stdout.splitlines()
        if (
            item.startswith(".changes/")
            and item.count("/") == 1
            and item.endswith(".rst")
        )
    )


def validate_commit_message(
    message: str,
    *,
    fragments_path: Path = FRAGMENTS_PATH,
    indexed_fragment_paths: list[Path] | None = None,
) -> list[Change]:
    """Require pending changelog language for a release-producing commit."""

    release_type = release_type_for_commit(message)
    if release_type is None:
        return []

    indexed_paths = (
        _indexed_fragment_paths()
        if indexed_fragment_paths is None
        else indexed_fragment_paths
    )
    if not indexed_paths:
        raise ChangelogError(
            f"this commit will create a semantic-release {release_type} release; "
            "stage a pending .changes/*.rst fragment before committing",
        )

    changes = validate_fragments(fragments_path)
    if release_type == "major" and not any(change.breaking for change in changes):
        raise ChangelogError(
            "a breaking commit requires a pending fragment entry that begins "
            "with 'Breaking:' after its category",
        )
    return changes


def parse_version(
    version: str, *, stable_only: bool = False
) -> tuple[int, int, int, str]:
    """Parse a semantic version used by semantic-release."""

    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ChangelogError(
            f"{version!r} is not a semantic version in MAJOR.MINOR.PATCH form",
        )
    suffix = match.group("suffix") or ""
    if stable_only and suffix:
        raise ChangelogError(
            f"stable changelog rendering cannot use prerelease {version!r}"
        )
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        suffix,
    )


def _release_versions(changelog_path: Path) -> list[tuple[int, int, int]]:
    """Read stable release versions already present in the changelog."""

    versions: list[tuple[int, int, int]] = []
    for line in changelog_path.read_text(encoding="utf-8").splitlines():
        match = RUBRIC_PATTERN.fullmatch(line)
        if match:
            versions.append(parse_version(match.group("version"), stable_only=True)[:3])
    if not versions:
        raise ChangelogError(f"{_display_path(changelog_path)} has no release entries")
    return versions


def _ensure_breaking_change(
    version: str,
    changes: list[Change],
    changelog_path: Path,
) -> bool:
    """Require a marked migration item when starting a new major line."""

    parsed_version = parse_version(version)
    latest_version = max(_release_versions(changelog_path))
    is_new_major = parsed_version[0] > latest_version[0]
    if is_new_major and not any(change.breaking for change in changes):
        raise ChangelogError(
            f"{version} starts SDK major {parsed_version[0]}; at least one "
            "fragment entry must begin with 'Breaking:' after its category",
        )
    return is_new_major


def _changed_fragment_paths(base: str, head: str) -> list[Path]:
    """Find fragment files changed between two Git references."""

    git_path = shutil.which("git")
    if git_path is None:
        raise ChangelogError("git is required to validate the changed PR fragment")
    result = subprocess.run(  # noqa: S603
        [
            git_path,
            "diff",
            "--name-only",
            "--diff-filter=ACMRTUXB",
            f"{base}...{head}",
        ],
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
    )
    changed: list[Path] = []
    for item in result.stdout.splitlines():
        if (
            item.startswith(".changes/")
            and item.count("/") == 1
            and item.endswith(".rst")
        ):
            changed.append(ROOT / item)
    return sorted(changed)


def validate_for_pull_request(
    base: str,
    head: str,
    *,
    version: str | None = None,
    fragments_path: Path = FRAGMENTS_PATH,
    changelog_path: Path = CHANGELOG_PATH,
) -> list[Change]:
    """Validate all fragments and require one fragment for a release PR."""

    changes = validate_fragments(fragments_path)
    changed_paths = _changed_fragment_paths(base, head)
    if len(changed_paths) != 1:
        joined_paths = ", ".join(str(_display_path(path)) for path in changed_paths)
        raise ChangelogError(
            "a release-producing pull request must change exactly one "
            f".changes/*.rst fragment; found {len(changed_paths)} ({joined_paths})",
        )

    if not changed_paths[0].exists():
        raise ChangelogError(
            f"{_display_path(changed_paths[0])} is deleted; add one current fragment",
        )

    changed_entries = _parse_fragment(changed_paths[0])
    if version:
        _ensure_breaking_change(version, changes, changelog_path)
    return changed_entries


def validate_no_pull_request_fragment(base: str, head: str) -> None:
    """Reject a fragment on a pull request that will not release."""

    changed_paths = _changed_fragment_paths(base, head)
    if changed_paths:
        joined_paths = ", ".join(str(_display_path(path)) for path in changed_paths)
        raise ChangelogError(
            "a pull request without a release must not add or modify a "
            f".changes/*.rst fragment ({joined_paths})",
        )


def _dropdown_ranges(lines: list[str]) -> list[tuple[int, int, int]]:
    """Return start/end indexes and major versions for dropdown blocks."""

    starts: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = DROPDOWN_PATTERN.fullmatch(line)
        if match:
            starts.append((index, int(match.group("major"))))
    return [
        (
            start,
            starts[position + 1][0] if position + 1 < len(starts) else len(lines),
            major,
        )
        for position, (start, major) in enumerate(starts)
    ]


def _entry_block(
    version: str,
    release_date: str,
    changes: list[Change],
    *,
    is_new_major: bool,
) -> list[str]:
    """Build an indented RST release entry."""

    block = [f"   .. rubric:: {version} ({release_date})", ""]
    if is_new_major:
        block.extend(["   **Breaking changes:**", ""])

    for position, change in enumerate(changes):
        block.extend(f"   {line}" if line else "" for line in change.lines)
        if position + 1 < len(changes):
            block.append("")
    block.append("")
    return block


def release_notes(
    *,
    version: str,
    changelog_path: Path = CHANGELOG_PATH,
    fragments_path: Path = FRAGMENTS_PATH,
) -> str:
    """Return release notes sourced from pending fragments without consuming them."""

    changes = validate_fragments(fragments_path)
    if not changes:
        raise ChangelogError("no pending .changes/*.rst fragments were found")
    is_new_major = _ensure_breaking_change(version, changes, changelog_path)

    notes: list[str] = []
    if is_new_major:
        notes.extend(["**Breaking changes:**", ""])
    for position, change in enumerate(changes):
        notes.extend(change.lines)
        if position + 1 < len(changes):
            notes.append("")
    return "\n".join(notes)


def render_changelog(
    *,
    version: str,
    release_date: str,
    changelog_path: Path = CHANGELOG_PATH,
    fragments_path: Path = FRAGMENTS_PATH,
) -> int:
    """Render and consume all pending fragments into one release entry."""

    parse_version(version, stable_only=True)
    if DATE_PATTERN.fullmatch(release_date) is None:
        raise ChangelogError(f"{release_date!r} is not an ISO date")
    try:
        date.fromisoformat(release_date)
    except ValueError as error:
        raise ChangelogError(f"{release_date!r} is not a valid ISO date") from error

    changes = validate_fragments(fragments_path)
    if not changes:
        raise ChangelogError("no pending .changes/*.rst fragments were found")

    lines = changelog_path.read_text(encoding="utf-8").splitlines()
    target_version = parse_version(version, stable_only=True)[:3]
    release_versions = _release_versions(changelog_path)
    if target_version in release_versions:
        raise ChangelogError(
            f"{version} already exists in {_display_path(changelog_path)}"
        )
    if target_version <= max(release_versions):
        raise ChangelogError(
            f"{version} is not newer than the latest changelog release "
            f"{'.'.join(str(part) for part in max(release_versions))}",
        )

    is_new_major = _ensure_breaking_change(version, changes, changelog_path)
    target_major = target_version[0]

    lines = [line for line in lines if line != "   :open:"]
    dropdowns = _dropdown_ranges(lines)
    matching_dropdown = next(
        (dropdown for dropdown in dropdowns if dropdown[2] == target_major),
        None,
    )
    if matching_dropdown is None:
        entry = _entry_block(
            version,
            release_date,
            changes,
            is_new_major=is_new_major,
        )
        new_dropdown = [f".. dropdown:: SDK {target_major}", "   :open:", ""]
        new_dropdown.extend(entry)
        first_dropdown = next(
            (
                index
                for index, line in enumerate(lines)
                if DROPDOWN_PATTERN.fullmatch(line)
            ),
            len(lines),
        )
        lines[first_dropdown:first_dropdown] = new_dropdown
    else:
        dropdown_start = matching_dropdown[0]
        lines.insert(dropdown_start + 1, "   :open:")
        refreshed_dropdowns = _dropdown_ranges(lines)
        target_dropdown = next(
            dropdown for dropdown in refreshed_dropdowns if dropdown[2] == target_major
        )
        first_rubric = next(
            (
                index
                for index in range(target_dropdown[0] + 1, target_dropdown[1])
                if RUBRIC_PATTERN.fullmatch(lines[index])
            ),
            target_dropdown[1],
        )
        lines[first_rubric:first_rubric] = _entry_block(
            version,
            release_date,
            changes,
            is_new_major=is_new_major,
        )

    changelog_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for path in fragment_paths(fragments_path):
        path.unlink()
    return len(changes)


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate pending fragments")
    validate.add_argument("--version", help="planned semantic-release version")
    pull_request_mode = validate.add_mutually_exclusive_group()
    pull_request_mode.add_argument(
        "--require-new",
        nargs=2,
        metavar=("BASE", "HEAD"),
        help="require exactly one fragment changed between two Git refs",
    )
    pull_request_mode.add_argument(
        "--forbid-new",
        nargs=2,
        metavar=("BASE", "HEAD"),
        help="reject fragments changed between two Git refs",
    )

    render = commands.add_parser("render", help="render and consume pending fragments")
    render.add_argument("--version", required=True)
    render.add_argument("--date", required=True, dest="release_date")

    notes = commands.add_parser(
        "notes", help="print release notes from pending fragments"
    )
    notes.add_argument("--version", required=True)

    commit = commands.add_parser(
        "validate-commit",
        help="require pending changelog language for release commits",
    )
    commit.add_argument("message_path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the changelog utility."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "validate-commit":
            changes = validate_commit_message(
                arguments.message_path.read_text(encoding="utf-8")
            )
            print(f"Validated commit changelog coverage ({len(changes)} item(s)).")
        elif arguments.command == "notes":
            print(release_notes(version=arguments.version))
        elif arguments.command == "render":
            count = render_changelog(
                version=arguments.version,
                release_date=arguments.release_date,
            )
            print(f"Rendered {arguments.version} from {count} changelog item(s).")
        elif arguments.require_new:
            validate_for_pull_request(
                arguments.require_new[0],
                arguments.require_new[1],
                version=arguments.version,
            )
            print("Validated all changelog fragments and exactly one PR fragment.")
        elif arguments.forbid_new:
            validate_fragments()
            validate_no_pull_request_fragment(
                arguments.forbid_new[0],
                arguments.forbid_new[1],
            )
            print("Validated all changelog fragments and found no PR fragment.")
        else:
            changes = validate_fragments()
            if arguments.version:
                _ensure_breaking_change(arguments.version, changes, CHANGELOG_PATH)
            count = len(changes)
            print(f"Validated {count} changelog item(s) in pending fragments.")
    except ChangelogError as error:
        print(f"changelog validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
