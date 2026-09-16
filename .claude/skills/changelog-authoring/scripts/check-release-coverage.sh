#!/usr/bin/env bash

set -euo pipefail

changelog_path="${1:-docs/changelog.rst}"
start_version="${2:-1.0.0}"

if [[ ! -f "$changelog_path" ]]; then
  echo "Changelog not found: $changelog_path" >&2
  exit 1
fi

stable_tags=()
stable_versions=()
while IFS= read -r tag; do
  version="${tag#v}"
  stable_tags+=("$tag")
  stable_versions+=("$version")
done < <(git tag --list --sort=version:refname | sed -nE '/^v?[0-9]+\.[0-9]+\.[0-9]+$/p')

start_index=-1
for index in "${!stable_versions[@]}"; do
  if [[ "${stable_versions[$index]}" == "$start_version" ]]; then
    start_index="$index"
    break
  fi
done

if (( start_index < 0 )); then
  echo "Stable tag not found: $start_version" >&2
  exit 1
fi

expected_versions=()
expected_dates=()
newest_version=""
for (( index = ${#stable_tags[@]} - 1; index >= start_index; index-- )); do
  expected_versions+=("${stable_versions[$index]}")
  expected_dates+=("$(git log -1 --format=%ad --date=short "${stable_tags[$index]}^{commit}")")
  if [[ -z "$newest_version" ]]; then
    newest_version="${stable_versions[$index]}"
  fi
done

actual_versions=()
actual_dates=()
while IFS=$'\t' read -r version date; do
  actual_versions+=("$version")
  actual_dates+=("$date")
done < <(sed -nE 's/^v?([0-9]+\.[0-9]+\.[0-9]+) \(([0-9]{4}-[0-9]{2}-[0-9]{2})\)$/\1\t\2/p' "$changelog_path")

actual_start_index=-1
for index in "${!actual_versions[@]}"; do
  if [[ "${actual_versions[$index]}" == "$start_version" ]]; then
    actual_start_index="$index"
    break
  fi
done

if (( actual_start_index < 0 )); then
  echo "Changelog heading not found: $start_version" >&2
  exit 1
fi

actual_count=$((actual_start_index + 1))
scoped_actual_versions=("${actual_versions[@]:0:actual_count}")
scoped_actual_dates=("${actual_dates[@]:0:actual_count}")

if [[ "${expected_versions[*]}" != "${scoped_actual_versions[*]}" ]]; then
  echo "Release headings do not match stable tags from $start_version." >&2
  diff -u \
    <(printf '%s\n' "${expected_versions[@]}") \
    <(printf '%s\n' "${scoped_actual_versions[@]}") || true
  exit 1
fi

date_mismatches=()
for index in "${!expected_dates[@]}"; do
  if [[ "${expected_dates[$index]}" != "${scoped_actual_dates[$index]}" ]]; then
    date_mismatches+=("${expected_versions[$index]}: expected ${expected_dates[$index]}, found ${scoped_actual_dates[$index]}")
  fi
done

if (( ${#date_mismatches[@]} > 0 )); then
  echo "Release heading dates do not match tag commit dates:" >&2
  printf '  %s\n' "${date_mismatches[@]}" >&2
  exit 1
fi

echo "Release coverage matches ${#expected_versions[@]} stable tags from $newest_version down to $start_version (newest to oldest)."
