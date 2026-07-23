import importlib
from collections.abc import Callable
from typing import Any

from soar_sdk.exceptions import AssetMisconfiguration
from soar_sdk.logging import getLogger

logger = getLogger()

CREDENTIAL_MANAGER_READABLE_NAME = {
    "cyberark_rest": "CyberARK API",
    "hashicorp": "Hashicorp Vault",
    "thycotic": "Thycotic Secret Server",
    "cyberark": "CyberARK SDK",
}

try:
    import phantom_common.credential_managers  # noqa: F401

    _soar_is_available = True
except ImportError:
    _soar_is_available = False


def _load_credential_manager(name: str) -> Callable | None:
    """Return the platform ``get_credential`` callable for a manager.

    Returns ``None`` only when running off-platform (local/CLI mode), where
    external credential managers are unavailable. On-platform load failures
    raise so the action does not proceed with unresolved credentials.
    """
    if not _soar_is_available:
        logger.warning(
            "Credential manager '%s' is not available in local mode; external credentials will not be fetched.",
            name,
        )
        return None
    module = importlib.import_module(f"phantom_common.credential_managers.{name}")
    return module.get_credential


def apply_credential_management(config: dict[str, Any], asset_id: str) -> list[str]:
    """Resolve credentials from an external manager into the asset config in place.

    Reads the ``_reserved_credential_management`` entry injected by the platform
    and, when present, fetches the configured fields from the external credential
    manager (e.g. Hashicorp Vault, CyberARK) and writes them over the directly
    configured values.

    Returns the names of the fields resolved from the manager, or an empty list
    when no credential management is configured (or when running off-platform).

    Raises:
        AssetMisconfiguration: If the configured manager cannot be loaded or a
            credential fetch fails. The action must not proceed in that case, as
            the directly configured values are intentionally overridden.
    """
    cred_mgmt = config.get("_reserved_credential_management")
    if not cred_mgmt:
        return []

    settings = cred_mgmt.get("settings", {})
    manager = settings.get("manager")
    manager_config = settings.get("config", {})
    fields = cred_mgmt.get("fields")
    if not manager or not fields:
        logger.debug("Credential manager not configured for asset %s", asset_id)
        return []

    readable_name = CREDENTIAL_MANAGER_READABLE_NAME.get(manager, manager)
    try:
        get_credential = _load_credential_manager(manager)
    except (ModuleNotFoundError, AttributeError) as e:
        raise AssetMisconfiguration(
            f"Failed to load credential manager '{readable_name}': {e}"
        ) from e
    if get_credential is None:
        return []

    try:
        if manager == "cyberark":
            resolved = []
            for field in fields:
                config[field["name"]] = get_credential(field, manager_config)
                resolved.append(field["name"])
            return resolved

        resolved = []
        for credential in get_credential(fields, manager_config):
            config[credential["name"]] = credential["value"]
            resolved.append(credential["name"])
        return resolved
    except Exception as e:
        raise AssetMisconfiguration(
            f"Credential manager failed to fetch values from {readable_name}: {e}"
        ) from e


__all__ = [
    "CREDENTIAL_MANAGER_READABLE_NAME",
    "apply_credential_management",
]
