from netrc import netrc
from types import SimpleNamespace

import httpx2
import pytest

from soar_sdk.meta.dependencies import index_auth
from soar_sdk.meta.dependencies.index_auth import UvIndexAuth

REGISTRY = "https://registry.example.org/simple"
ARTIFACT = "https://registry.example.org/files/dependency.whl"


@pytest.fixture(autouse=True)
def isolate_uv_config(tmp_path, monkeypatch):
    monkeypatch.delenv("UV_CONFIG_FILE", raising=False)
    monkeypatch.delenv("UV_NO_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user"))
    monkeypatch.setenv("XDG_CONFIG_DIRS", str(tmp_path / "system"))
    monkeypatch.setenv("NETRC", str(tmp_path / "missing.netrc"))


@pytest.fixture
def netrc_file(tmp_path, monkeypatch):
    path = tmp_path / "credentials.netrc"
    path.write_text("machine registry.example.org login user password pass\n")
    path.chmod(0o600)
    monkeypatch.setenv("NETRC", str(path))
    return path


def _authorization(index_auth, registry=REGISTRY, artifact=ARTIFACT):
    auth = index_auth.for_registry(registry)
    if auth is None or (basic_auth := auth.for_artifact(artifact)) is None:
        return None
    request = httpx2.Request("GET", artifact)
    return next(basic_auth.auth_flow(request)).headers["Authorization"]


def test_reads_legacy_index_urls_from_system_config(tmp_path):
    config = tmp_path / "system" / "uv" / "uv.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        'index-url = "https://user:pass@registry.example.org/simple/"\n'
        'extra-index-url = ["https://repo:token@extra.example.org/simple/"]\n'
    )

    auth = UvIndexAuth(tmp_path)

    assert _authorization(auth) == "Basic dXNlcjpwYXNz"
    assert (
        _authorization(
            auth,
            "https://extra.example.org/simple",
            "https://extra.example.org/files/dependency.whl",
        )
        == "Basic cmVwbzp0b2tlbg=="
    )
    assert _authorization(auth, "https://registry.example.org/other/simple") is None
    assert _authorization(auth, None) is None


@pytest.mark.parametrize(
    "artifact",
    [
        "https://different.example.org/wheel.whl",
        "https://registry.example.org:1234/wheel.whl",
        "http://registry.example.org/wheel.whl",
        "https://direct:token@registry.example.org/wheel.whl",
    ],
)
def test_registry_credentials_are_not_used_for_other_origins_or_direct_auth(
    tmp_path, artifact
):
    (tmp_path / "uv.toml").write_text(
        '[[index]]\nurl = "https://user:pass@registry.example.org/simple"\n'
    )

    assert _authorization(UvIndexAuth(tmp_path), artifact=artifact) is None


def test_config_file_and_no_config(tmp_path, monkeypatch):
    config = tmp_path / "custom.toml"
    config.write_text(
        '[[index]]\nurl = "https://user:p%40ss@registry.example.org/simple"\n'
    )
    (tmp_path / "uv.toml").write_text(
        '[[index]]\nurl = "https://another:secret@registry.example.org/simple"\n'
    )
    monkeypatch.setenv("UV_CONFIG_FILE", str(config))

    assert _authorization(UvIndexAuth(tmp_path)) == "Basic dXNlcjpwQHNz"

    monkeypatch.setenv("UV_NO_CONFIG", "true")

    assert _authorization(UvIndexAuth(tmp_path)) is None


def test_inherited_project_config_overrides_system_default_index(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "example"\n')
    (tmp_path / "uv.toml").write_text(
        'index-url = "https://user:pass@registry.example.org/simple/"\n'
    )
    system_config = tmp_path / "system" / "uv" / "uv.toml"
    system_config.parent.mkdir(parents=True)
    system_config.write_text(
        'index-url = "https://another:secret@registry.example.org/simple"\n'
    )

    assert _authorization(UvIndexAuth(project)) == "Basic dXNlcjpwYXNz"


def test_project_index_overrides_user_index(tmp_path, monkeypatch):
    user_config = tmp_path / "user" / "uv" / "uv.toml"
    user_config.parent.mkdir(parents=True)
    user_config.write_text(
        '[[index]]\nurl = "https://another:secret@registry.example.org/simple"\n'
        '[[index]]\nname = "internal-proxy"\nurl = "https://another:secret@other.example.org/simple"\n'
    )
    (tmp_path / "pyproject.toml").write_text(
        '[[tool.uv.index]]\nname = "internal-proxy"\n'
        'url = "https://registry.example.org/simple"\n'
    )
    monkeypatch.setenv("UV_INDEX_INTERNAL_PROXY_USERNAME", "user")
    monkeypatch.setenv("UV_INDEX_INTERNAL_PROXY_PASSWORD", "pass")

    auth = UvIndexAuth(tmp_path)

    assert _authorization(auth) == "Basic dXNlcjpwYXNz"
    assert _authorization(auth, "https://other.example.org/simple") is None


def test_project_uv_toml_overrides_pyproject_and_disables_auth(
    tmp_path, monkeypatch, netrc_file
):
    (tmp_path / "pyproject.toml").write_text(
        '[[tool.uv.index]]\nurl = "https://user:pass@registry.example.org/simple"\n'
    )
    (tmp_path / "uv.toml").write_text(
        '[[index]]\nname = "internal-proxy"\nauthenticate = "never"\n'
        'url = "https://registry.example.org/simple"\n'
    )
    monkeypatch.setenv("UV_INDEX_INTERNAL_PROXY_USERNAME", "user")
    monkeypatch.setenv("UV_INDEX_INTERNAL_PROXY_PASSWORD", "pass")

    assert _authorization(UvIndexAuth(tmp_path)) is None


@pytest.mark.parametrize("status_code", [200, 401, 403, 404, 500])
def test_netrc_credentials_retry_an_authentication_challenge(
    tmp_path, monkeypatch, netrc_file, status_code
):
    monkeypatch.setenv("UV_NO_CONFIG", "1")
    auth = UvIndexAuth(tmp_path).for_registry(REGISTRY)
    assert auth is not None
    assert auth.for_artifact("https://other.example.org/files/dependency.whl") is None
    headers = []

    def respond(request):
        headers.append(request.headers.get("Authorization"))
        return httpx2.Response(200 if headers[-1] else status_code)

    with httpx2.Client(transport=httpx2.MockTransport(respond)) as client:
        response = client.get(ARTIFACT, auth=auth.for_artifact(ARTIFACT))

    if status_code in (401, 403, 404):
        assert response.status_code == 200
        assert headers == [None, "Basic dXNlcjpwYXNz"]
    else:
        assert response.status_code == status_code
        assert headers == [None]


@pytest.mark.parametrize(
    ("index_url", "expected_auth"),
    [
        ("https://registry.example.org/simple", "Basic dXNlcjpwYXNz"),
        ("https://user@registry.example.org/simple", "Basic dXNlcjpwYXNz"),
        ("https://other@registry.example.org/simple", "Basic b3RoZXI6"),
        (
            "https://user:preferred@registry.example.org/simple",
            "Basic dXNlcjpwcmVmZXJyZWQ=",
        ),
    ],
)
def test_netrc_respects_explicit_credentials_and_always_policy(
    tmp_path, netrc_file, index_url, expected_auth
):
    (tmp_path / "uv.toml").write_text(
        f'[[index]]\nurl = "{index_url}"\nauthenticate = "always"\n'
    )

    assert _authorization(UvIndexAuth(tmp_path)) == expected_auth


def test_netrc_uses_default_file_when_environment_variable_is_unset(
    tmp_path, monkeypatch, mocker, netrc_file
):
    monkeypatch.delenv("NETRC")
    netrc_file.write_text("default login user password pass\n")
    reader = mocker.patch.object(index_auth, "netrc", return_value=netrc(netrc_file))
    (tmp_path / "uv.toml").write_text(
        '[[index]]\nurl = "https://registry.example.org/simple"\nauthenticate = "always"\n'
    )

    assert _authorization(UvIndexAuth(tmp_path)) == "Basic dXNlcjpwYXNz"
    reader.assert_called_once_with(None)


def test_invalid_netrc_reports_error_without_disclosing_content(
    tmp_path, netrc_file, caplog
):
    netrc_file.write_text("machine registry.example.org login user invalid-secret\n")

    assert _authorization(UvIndexAuth(tmp_path)) is None
    assert "Could not read .netrc credentials" in caplog.text
    assert "invalid-secret" not in caplog.text


def test_windows_user_and_system_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(index_auth, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "user"))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "system"))
    for level in ("user", "system"):
        config = tmp_path / level / "uv" / "uv.toml"
        config.parent.mkdir(parents=True)
        config.write_text(
            f'[[index]]\nurl = "https://user:{level}@registry.example.org/simple"\n'
        )

    assert _authorization(UvIndexAuth(tmp_path)) == "Basic dXNlcjp1c2Vy"
