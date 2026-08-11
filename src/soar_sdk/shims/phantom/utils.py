try:
    from phantom.utils import (
        CONTAINS_VALIDATORS,
        is_domain,
        is_email,
        is_hash,
        is_hostname,
        is_ip,
        is_mac,
        is_md5,
        is_sha1,
        is_sha256,
        is_sha512,
        is_url,
    )

    _soar_is_available = True
except ImportError:
    _soar_is_available = False

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING or not _soar_is_available:

    def is_mac(mac_str: str) -> bool:
        """Validates if the input is a MAC address."""
        mac_regex = r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$"
        return bool(re.match(mac_regex, mac_str, re.IGNORECASE))

    def is_sha1(input_str: str) -> bool:
        """Validates if the input is a sha1 hash."""
        return bool(re.match(r"^[0-9a-fA-F]{40}$", input_str))

    def is_sha256(input_str: str) -> bool:
        """Validates if the input is a sha256 hash."""
        return bool(re.match(r"^[0-9a-fA-F]{64}$", input_str))

    def is_sha512(input_str: str) -> bool:
        """Validates if the input is a sha512 hash."""
        return bool(re.match(r"^[0-9a-fA-F]{128}$", input_str))

    def is_md5(input_str: str) -> bool:
        """Validates if the input is a md5 hash."""
        return bool(re.match(r"^[0-9a-fA-F]{32}$", input_str))

    def is_ip(ip_str: str) -> bool:
        """Validates if the input is compliant with the IPv4 standard."""
        ip_regex = r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
        return bool(re.match(ip_regex, ip_str))

    def is_hash(hash_str: str) -> bool:
        """Validates if the input is a hash of sha1, sha256, sha512, or md5 type."""
        return (
            is_sha1(hash_str)
            or is_sha256(hash_str)
            or is_sha512(hash_str)
            or is_md5(hash_str)
        )

    def is_url(input_str: str) -> bool:
        """Validates if the input is compliant with the URL standard."""
        regex = r"^[A-Z][0-9A-Z+\-.]*://.*$"
        return bool(re.match(regex, input_str, re.IGNORECASE | re.UNICODE))

    def is_domain(hostname: str) -> bool:
        """Validates if the input is accepted as a domain name."""
        if len(hostname) > 255:
            return False
        if is_ip(hostname):
            return False
        if hostname[-1] == ".":
            hostname = hostname[:-1]
        allowed = re.compile("@", re.IGNORECASE | re.UNICODE)
        return not any(allowed.search(x) for x in hostname.split("."))

    def is_hostname(hostname: str) -> bool:
        """Overload of is_domain()."""
        if len(hostname) > 255:
            return False
        if is_ip(hostname):
            return False
        if hostname[-1] == ".":
            hostname = hostname[:-1]
        allowed = re.compile("@", re.IGNORECASE | re.UNICODE)
        return not any(allowed.match(x) for x in hostname.split("."))

    def is_email(email_str: str) -> bool:
        """Validates if the input is accepted as an email address."""
        if len(email_str) > 255:
            return False
        return re.match(r"^\S+@\S+\.\S+$", email_str) is not None

    CONTAINS_VALIDATORS = {
        "domain": is_domain,
        "ip": is_ip,
        "hash": is_hash,
        "sha1": is_sha1,
        "sha256": is_sha256,
        "sha512": is_sha512,
        "md5": is_md5,
        "host name": is_hostname,
        "mac address": is_mac,
        "url": is_url,
        "email": is_email,
    }

__all__ = [
    "CONTAINS_VALIDATORS",
    "is_domain",
    "is_email",
    "is_hash",
    "is_hostname",
    "is_ip",
    "is_mac",
    "is_md5",
    "is_sha1",
    "is_sha256",
    "is_sha512",
    "is_url",
]
