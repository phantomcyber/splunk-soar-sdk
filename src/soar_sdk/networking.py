import ipaddress
from typing import Annotated

from pydantic import AfterValidator

_INVALID_HOST_MESSAGE = "Value must be a valid IP address or hostname"


def _normalize_host(value: str) -> str:
    candidate = value.strip()
    if not candidate or candidate.lower().startswith(("http://", "https://")):
        raise ValueError(_INVALID_HOST_MESSAGE)

    candidate = candidate.rstrip("/")
    if not candidate or len(candidate) > 253:
        raise ValueError(_INVALID_HOST_MESSAGE)

    ip_candidate = candidate
    if candidate.startswith("[") and candidate.endswith("]"):
        ip_candidate = candidate[1:-1]

    try:
        return ipaddress.ip_address(ip_candidate).compressed
    except ValueError:
        pass

    if (
        not any(char.isalnum() for char in candidate)
        or any(char.isspace() for char in candidate)
        or any(char in "/:@?#[]\\" for char in candidate)
    ):
        raise ValueError(_INVALID_HOST_MESSAGE)

    return candidate.removesuffix(".").lower()


Host = Annotated[str, AfterValidator(_normalize_host)]
"""A normalized IP address or hostname for use in Pydantic models."""


def format_url_host(host: str) -> str:
    """Format a normalized host for use in a URL authority."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    return f"[{address.compressed}]" if address.version == 6 else address.compressed


__all__ = ["Host", "format_url_host"]
