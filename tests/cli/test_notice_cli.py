import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from typer.testing import CliRunner

from soar_sdk.cli.manifests.cli import manifests
from soar_sdk.cli.manifests.notice import NoticeGenerator

runner = CliRunner()

SAMPLE_LICENSE_ENTRIES = [
    {
        "Name": "requests",
        "Version": "2.32.0",
        "License": "Apache Software License",
        "URL": "https://requests.readthedocs.io",
        "LicenseText": "Apache License\nVersion 2.0\n",
        "NoticeText": None,
    },
    {
        "Name": "certifi",
        "Version": "2024.2.2",
        "License": "MPL-2.0",
        "URL": "https://github.com/certifi/python-certifi",
        "LicenseText": None,
        "NoticeText": None,
    },
    {
        "Name": "charset-normalizer",
        "Version": "3.3.2",
        "License": "MIT",
        "URL": "https://github.com/Ousret/charset_normalizer",
        "LicenseText": "MIT License\nCopyright...\n",
        "NoticeText": "NOTICE text here",
    },
]


# ── CLI command tests ──────────────────────────────────────────────────────────


def test_create_notice_happy_path(tmp_path):
    with patch.object(NoticeGenerator, "generate") as mock_generate:
        result = runner.invoke(manifests, ["create-notice", str(tmp_path)])

    assert result.exit_code == 0, result.output
    mock_generate.assert_called_once_with(tmp_path / "NOTICE")


def test_create_notice_default_output_path(tmp_path):
    with patch.object(NoticeGenerator, "generate") as mock_generate:
        runner.invoke(manifests, ["create-notice", str(tmp_path)])

    mock_generate.assert_called_once_with(tmp_path / "NOTICE")


def test_create_notice_custom_output_file(tmp_path):
    custom_out = tmp_path / "subdir" / "MY_NOTICE"
    with patch.object(NoticeGenerator, "generate") as mock_generate:
        result = runner.invoke(
            manifests,
            ["create-notice", str(tmp_path), "--output-file", str(custom_out)],
        )

    assert result.exit_code == 0, result.output
    mock_generate.assert_called_once_with(custom_out)


def test_create_notice_custom_output_file_short_flag(tmp_path):
    custom_out = tmp_path / "MY_NOTICE"
    with patch.object(NoticeGenerator, "generate") as mock_generate:
        result = runner.invoke(
            manifests,
            ["create-notice", str(tmp_path), "-o", str(custom_out)],
        )

    assert result.exit_code == 0, result.output
    mock_generate.assert_called_once_with(custom_out)


# ── NoticeGenerator.generate validation tests ─────────────────────────────────


def test_generate_missing_pyproject(tmp_path):
    gen = NoticeGenerator(tmp_path)
    with pytest.raises(click.exceptions.Exit):
        gen.generate(tmp_path / "NOTICE")


def test_generate_missing_uv_lock(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    gen = NoticeGenerator(tmp_path)
    with pytest.raises(click.exceptions.Exit):
        gen.generate(tmp_path / "NOTICE")


def test_generate_missing_venv(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "uv.lock").write_text("")
    gen = NoticeGenerator(tmp_path)
    with pytest.raises(click.exceptions.Exit):
        gen.generate(tmp_path / "NOTICE")


def test_generate_pip_licenses_failure(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / ".venv").mkdir()

    gen = NoticeGenerator(tmp_path)
    with (
        patch.object(
            gen, "get_app_name_and_license", return_value=("My App", "Apache-2.0")
        ),
        patch.object(gen, "get_dependency_names", return_value=["requests"]),
        patch.object(
            gen,
            "get_license_info",
            side_effect=subprocess.CalledProcessError(
                1, "pip-licenses", stderr="error"
            ),
        ),
        pytest.raises(click.exceptions.Exit),
    ):
        gen.generate(tmp_path / "NOTICE")


def test_generate_writes_notice_file(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / ".venv").mkdir()
    output = tmp_path / "NOTICE"

    gen = NoticeGenerator(tmp_path)
    with (
        patch.object(
            gen, "get_app_name_and_license", return_value=("My App", "Apache-2.0")
        ),
        patch.object(gen, "get_dependency_names", return_value=["requests"]),
        patch.object(gen, "get_license_info", return_value=SAMPLE_LICENSE_ENTRIES),
    ):
        gen.generate(output)

    assert output.exists()
    content = output.read_text()
    assert content.startswith("Splunk SOAR App: My App\nApache-2.0\n")
    assert "Third Party Software Attributions:" in content


def test_generate_empty_dependencies(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / ".venv").mkdir()
    output = tmp_path / "NOTICE"

    gen = NoticeGenerator(tmp_path)
    with (
        patch.object(gen, "get_app_name_and_license", return_value=("My App", "MIT")),
        patch.object(gen, "get_dependency_names", return_value=[]),
    ):
        gen.generate(output)

    content = output.read_text()
    assert "Splunk SOAR App: My App" in content
    assert "Third Party Software Attributions" not in content


# ── NoticeGenerator._format_notice unit tests ─────────────────────────────────


def test_format_notice_header():
    gen = NoticeGenerator(Path())
    result = gen._format_notice("My App", "Apache-2.0", [])
    assert result == "Splunk SOAR App: My App\nApache-2.0\n"


def test_format_notice_with_entries():
    gen = NoticeGenerator(Path())
    result = gen._format_notice("My App", "Apache-2.0", SAMPLE_LICENSE_ENTRIES)

    assert "Splunk SOAR App: My App\nApache-2.0\n" in result
    assert "Third Party Software Attributions:" in result
    assert (
        "@@@@============================================================================"
        in result
    )
    assert "Library: requests - 2.32.0" in result
    assert "Homepage: https://requests.readthedocs.io" in result
    assert "License: Apache Software License" in result
    assert "Apache License\nVersion 2.0" in result


def test_format_notice_unknown_license_text_fallback():
    gen = NoticeGenerator(Path())
    entries = [
        {
            "Name": "certifi",
            "Version": "2024.2.2",
            "License": "MPL-2.0",
            "URL": "https://github.com/certifi/python-certifi",
            "LicenseText": None,
            "NoticeText": None,
        }
    ]
    result = gen._format_notice("My App", "MIT", entries)
    assert (
        "Please navigate to https://github.com/certifi/python-certifi to obtain a copy of the license."
        in result
    )


def test_format_notice_with_notice_text():
    gen = NoticeGenerator(Path())
    entries = [
        {
            "Name": "charset-normalizer",
            "Version": "3.3.2",
            "License": "MIT",
            "URL": "https://example.com",
            "LicenseText": "MIT License",
            "NoticeText": "NOTICE text here",
        }
    ]
    result = gen._format_notice("My App", "MIT", entries)
    assert "Notice:\n\nNOTICE text here" in result


def test_format_notice_without_notice_text():
    gen = NoticeGenerator(Path())
    entries = [
        {
            "Name": "requests",
            "Version": "2.32.0",
            "License": "Apache-2.0",
            "URL": "https://example.com",
            "LicenseText": "Apache License",
            "NoticeText": None,
        }
    ]
    result = gen._format_notice("My App", "MIT", entries)
    assert "Notice:" not in result


# ── NoticeGenerator._post_process unit tests ──────────────────────────────────


def test_post_process_strips_trailing_whitespace():
    gen = NoticeGenerator(Path())
    result = gen._post_process("line one   \nline two  \n")
    assert result == "line one\nline two\n"


def test_post_process_removes_trailing_blank_lines():
    gen = NoticeGenerator(Path())
    result = gen._post_process("content\n\n\n")
    assert result == "content\n"


def test_post_process_ends_with_newline():
    gen = NoticeGenerator(Path())
    result = gen._post_process("content")
    assert result.endswith("\n")


# ── NoticeGenerator.get_license_info unit tests ───────────────────────────────


def test_get_license_info_parses_json(tmp_path):
    import json as json_mod

    raw = [
        {
            "Name": "requests",
            "Version": "2.32.0",
            "License": "Apache-2.0",
            "URL": "https://example.com",
            "LicenseText": "Apache",
            "NoticeText": "UNKNOWN",
        },
        {
            "Name": "six",
            "Version": "1.16.0",
            "License": "MIT",
            "URL": "https://example.com",
            "LicenseText": "UNKNOWN",
            "NoticeText": "UNKNOWN",
        },
        # Entry where LicenseText is UNKNOWN but NoticeText is not (covers branch at line 65)
        {
            "Name": "certifi",
            "Version": "2024.2.2",
            "License": "MPL-2.0",
            "URL": "https://example.com",
            "LicenseText": "UNKNOWN",
            "NoticeText": "some notice",
        },
    ]

    mock_result = MagicMock()
    mock_result.stdout = json_mod.dumps(raw)

    gen = NoticeGenerator(tmp_path)
    with (
        patch("shutil.which", return_value="/usr/bin/uv"),
        patch("subprocess.run", return_value=mock_result),
    ):
        entries = gen.get_license_info(["requests", "six", "certifi"])

    assert len(entries) == 3
    # UNKNOWN normalized to None
    assert entries[0]["NoticeText"] is None
    assert entries[1]["LicenseText"] is None
    # LicenseText UNKNOWN but NoticeText kept as-is
    assert entries[2]["LicenseText"] is None
    assert entries[2]["NoticeText"] == "some notice"


def test_get_license_info_no_uv(tmp_path):
    gen = NoticeGenerator(tmp_path)
    with patch("shutil.which", return_value=None), pytest.raises(click.exceptions.Exit):
        gen.get_license_info(["requests"])


# ── NoticeGenerator.get_app_name_and_license / get_dependency_names ───────────


def test_get_app_name_and_license(tmp_path):
    mock_app = MagicMock()
    mock_app.app_meta_info = {"name": "My App"}
    mock_app_meta = MagicMock()
    mock_app_meta.license = "Apache-2.0"

    gen = NoticeGenerator(tmp_path)
    with (
        patch("soar_sdk.cli.manifests.notice.ManifestProcessor") as MockProcessor,
    ):
        instance = MockProcessor.return_value
        instance.load_toml_app_meta.return_value = mock_app_meta
        instance.import_app_instance.return_value = mock_app
        name, lic = gen.get_app_name_and_license()

    assert name == "My App"
    assert lic == "Apache-2.0"


def test_get_dependency_names(tmp_path):
    mock_pkg_a = MagicMock()
    mock_pkg_a.name = "requests"
    mock_pkg_b = MagicMock()
    mock_pkg_b.name = "certifi"
    mock_app_meta = MagicMock()
    mock_app_meta.project_name = "myapp"
    mock_uv_lock = MagicMock()
    mock_uv_lock.build_package_list.return_value = [mock_pkg_a, mock_pkg_b]

    gen = NoticeGenerator(tmp_path)
    with (
        patch("soar_sdk.cli.manifests.notice.ManifestProcessor") as MockProcessor,
    ):
        instance = MockProcessor.return_value
        instance.load_toml_app_meta.return_value = mock_app_meta
        instance.load_app_uv_lock.return_value = mock_uv_lock
        names = gen.get_dependency_names()

    assert names == ["requests", "certifi"]
    mock_uv_lock.build_package_list.assert_called_once_with("myapp")
