import hashlib
import ipaddress
import json
import re
from email.header import decode_header, make_header
from pathlib import Path
from typing import Any

from bs4 import UnicodeDammit  # type: ignore[attr-defined]

from soar_sdk.logging import getLogger

logger = getLogger()

FILE_EXTENSIONS = {
    ".vmsn": ["os memory dump", "vm snapshot file"],
    ".vmss": ["os memory dump", "vm suspend file"],
    ".js": ["javascript"],
    ".doc": ["doc"],
    ".docx": ["doc"],
    ".xls": ["xls"],
    ".xlsx": ["xls"],
}

MAGIC_FORMATS = [
    ("^PE.* Windows", ["pe file", "hash"]),
    ("^MS-DOS executable", ["pe file", "hash"]),
    ("^PDF ", ["pdf"]),
    ("^MDMP crash", ["process dump"]),
    ("^Macromedia Flash", ["flash"]),
]


def get_file_contains(file_path: str) -> list[str]:
    """Get file type contains based on extension and magic bytes."""
    try:
        import magic  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "python-magic not installed, file type detection will be limited"
        )
        return []

    contains = []
    ext = Path(file_path).suffix
    contains.extend(FILE_EXTENSIONS.get(ext, []))

    try:
        magic_str = magic.from_file(file_path)
        for regex_pattern, cur_contains in MAGIC_FORMATS:
            if re.match(regex_pattern, magic_str):
                contains.extend(cur_contains)
    except Exception as e:
        logger.debug(f"Failed to detect file type with magic: {e}")

    return contains


def is_ip(input_ip: str) -> bool:
    """Check if input is a valid IP address."""
    try:
        ipaddress.ip_address(input_ip)
        return True
    except ValueError:
        return False


def is_ipv6(input_ip: str) -> bool:
    """Validate if input is an IPv6 address."""
    try:
        ip = ipaddress.ip_address(input_ip)
        return ip.version == 6
    except ValueError:
        return False


def is_sha1(input_str: str) -> bool:
    """Validate if the input is a SHA1 hash."""
    sha1_regex = r"^[0-9a-fA-F]{40}$"
    return bool(re.match(sha1_regex, input_str))


def clean_url(url: str) -> str:
    """Clean and normalize a URL string."""
    url = url.strip(">),.]\r\n")
    if "<" in url:
        url = url[: url.find("<")]
    if ">" in url:
        url = url[: url.find(">")]
    url = url.rstrip("]")
    return url.strip()


def decode_uni_string(input_str: str, def_name: str) -> str:
    """Decode RFC 2047 encoded strings."""
    encoded_strings = re.findall(r"=\?.*?\?=", input_str, re.I)

    if not encoded_strings:
        return input_str

    try:
        decoded_strings = [decode_header(x)[0] for x in encoded_strings]
        decoded_string_dicts = [
            {"value": x[0], "encoding": x[1]} for x in decoded_strings
        ]
    except Exception as e:
        logger.debug(f"Decoding: {encoded_strings}. Error: {e}")
        return def_name

    new_str = ""
    new_str_create_count = 0
    for _i, decoded_string_dict in enumerate(decoded_string_dicts):
        value = decoded_string_dict.get("value")
        encoding = decoded_string_dict.get("encoding")

        if not encoding or not value:
            continue

        try:
            if encoding != "utf-8":
                value = str(value, encoding)
        except Exception as e:
            logger.debug(f"Encoding conversion failed: {e}")

        try:
            new_str += UnicodeDammit(value).unicode_markup
            new_str_create_count += 1
        except Exception as e:
            logger.debug(f"Unicode markup conversion failed: {e}")

    if new_str and new_str_create_count == len(encoded_strings):
        logger.debug(
            "Creating a new string entirely from the encoded_strings and assigning into input_str"
        )
        input_str = new_str

    return input_str


def get_string(input_str: str, charset: str | None = None) -> str:
    """Convert string to proper encoding with charset handling."""
    if not input_str:
        return input_str

    if charset is None:
        charset = "utf-8"

    try:
        return UnicodeDammit(input_str).unicode_markup.encode(charset).decode(charset)
    except Exception:
        try:
            return str(make_header(decode_header(input_str)))
        except Exception:
            return decode_uni_string(input_str, input_str)


def remove_child_info(file_path: str) -> str:
    """Remove child info suffix from file path."""
    if file_path.endswith("_True"):
        return file_path.rstrip("_True")
    return file_path.rstrip("_False")


def create_dict_hash(input_dict: dict[str, Any]) -> str | None:
    """Create a SHA256 hash of a dictionary."""
    if not input_dict:
        return None

    try:
        input_dict_str = json.dumps(input_dict, sort_keys=True)
    except Exception as e:
        logger.debug(f"Handled exception in create_dict_hash: {e}")
        return None

    try:
        return hashlib.sha256(input_dict_str).hexdigest()  # type: ignore[arg-type]
    except TypeError:
        return hashlib.sha256(input_dict_str.encode("UTF-8")).hexdigest()
