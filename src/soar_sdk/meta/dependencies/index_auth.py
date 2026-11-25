__lazy_modules__ = {
    "collections.abc",
    "httpx2",
    "logging",
    "netrc",
    "os",
    "pathlib",
    "re",
    "sys",
    "tomllib",
    "typing",
}

import os
import re
import sys
import tomllib
from collections.abc import Generator, Iterator
from logging import getLogger
from netrc import NetrcParseError, netrc
from pathlib import Path
from typing import NotRequired, TypedDict, cast

import httpx2

logger = getLogger("soar_sdk.meta.dependencies")


class _Index(TypedDict):
    url: str
    name: NotRequired[str]
    authenticate: NotRequired[str]


def _registry_key(url: httpx2.URL) -> httpx2.URL:
    path, separator, query = url.raw_path.partition(b"?")
    return url.copy_with(
        username=None,
        password=None,
        raw_path=(path.rstrip(b"/") or b"/") + separator + query,
    )


def _origin(url: httpx2.URL) -> tuple[str, str, int | None]:
    return url.scheme, url.host, url.port


class RegistryAuth:
    """Credentials for the artifacts served by a single registry origin."""

    def __init__(self, registry: httpx2.URL, auth: httpx2.BasicAuth) -> None:
        self._origin = _origin(registry)
        self._auth = auth

    def for_artifact(self, url: str) -> httpx2.BasicAuth | None:
        """Return credentials only for same-origin artifacts without their own auth."""
        artifact = httpx2.URL(url)
        if _origin(artifact) == self._origin and not artifact.userinfo:
            return self._auth
        return None


class _NetrcChallengeAuth(httpx2.BasicAuth):
    def auth_flow(
        self, request: httpx2.Request
    ) -> Generator[httpx2.Request, httpx2.Response]:
        response = yield request
        # Private registries may return 404 for unauthenticated requests.
        if response.status_code in (401, 403, 404):
            yield from super().auth_flow(request)


def _read_netrc() -> netrc | None:
    try:
        return netrc(os.getenv("NETRC"))
    except FileNotFoundError:
        return None
    except (OSError, NetrcParseError, UnicodeError):
        logger.warning("Could not read .netrc credentials")
        return None


def _read_config(path: Path) -> dict[str, object]:
    with path.open("rb") as file:
        return tomllib.load(file)


def _uv_settings(project: Path) -> Iterator[dict[str, object]]:
    if os.getenv("UV_NO_CONFIG") in ("1", "true"):
        return
    if config_file := os.getenv("UV_CONFIG_FILE"):
        yield _read_config(Path(config_file))
        return

    for directory in (project, *project.parents):
        config = directory / "uv.toml"
        if config.is_file():
            yield _read_config(config)
            break
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            tool = cast("dict[str, object]", _read_config(pyproject).get("tool", {}))
            if "uv" in tool:
                yield cast("dict[str, object]", tool["uv"])
                break

    if sys.platform == "win32":
        user_config = Path(os.environ["APPDATA"]) / "uv" / "uv.toml"
        system_dirs = [os.environ["PROGRAMDATA"]]
    else:
        user_config = (
            Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
            / "uv"
            / "uv.toml"
        )
        system_dirs = (os.getenv("XDG_CONFIG_DIRS") or "").split(os.pathsep)
        system_dirs.append("/etc")
    if user_config.is_file():
        yield _read_config(user_config)

    for system_dir in filter(None, system_dirs):
        config = Path(system_dir) / "uv" / "uv.toml"
        if config.is_file():
            yield _read_config(config)
            break


def _configured_indexes(project: Path) -> Iterator[_Index]:
    default_index: str | None = None
    for settings in _uv_settings(project):
        yield from cast("list[_Index]", settings.get("index", []))
        for url in cast("list[str]", settings.get("extra-index-url", [])):
            yield {"url": url}
        if default_index is None:
            default_index = cast("str | None", settings.get("index-url"))
    if default_index:
        yield {"url": default_index}


class UvIndexAuth:
    """Load configured uv index credentials without altering locked artifact URLs."""

    def __init__(self, project: Path) -> None:
        self._netrc = _read_netrc()
        self._registries: dict[httpx2.URL, RegistryAuth | None] = {}
        names: set[str] = set()
        for index in _configured_indexes(project):
            url = httpx2.URL(index["url"])
            key = _registry_key(url)
            name = index.get("name")
            if key in self._registries or (name is not None and name in names):
                continue
            if name is not None:
                names.add(name)
            self._registries[key] = None
            if index.get("authenticate") == "never":
                continue
            username, password = url.username, url.password
            if name is not None:
                env_prefix = "UV_INDEX_" + re.sub(r"[^A-Z0-9]", "_", name.upper())
                username = os.getenv(f"{env_prefix}_USERNAME", username)
                password = os.getenv(f"{env_prefix}_PASSWORD", password)
            if password:
                auth = RegistryAuth(url, httpx2.BasicAuth(username, password))
            else:
                auth = self._netrc_auth(
                    url, username, eager=index.get("authenticate") == "always"
                )
                if auth is None and username:
                    auth = RegistryAuth(url, httpx2.BasicAuth(username, ""))
            self._registries[key] = auth

    def _netrc_auth(
        self, registry: httpx2.URL, username: str = "", *, eager: bool = False
    ) -> RegistryAuth | None:
        if self._netrc is None:
            return None
        entry = self._netrc.authenticators(registry.host)
        if entry is None:
            return None
        login, _, password = entry
        if username and username != login:
            return None
        auth_type = httpx2.BasicAuth if eager or username else _NetrcChallengeAuth
        return RegistryAuth(registry, auth_type(login, password))

    def for_registry(self, registry: str | None) -> RegistryAuth | None:
        """Look up credentials for the exact index recorded in the lockfile."""
        if registry is None:
            return None
        url = httpx2.URL(registry)
        key = _registry_key(url)
        if key in self._registries:
            return self._registries[key]
        return self._netrc_auth(url)
