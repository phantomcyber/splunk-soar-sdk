"""Jinja filters and functions for SOAR SDK templates. (ported and modified from platform custom_template.py)"""

import hashlib
import json
import re
import uuid
import humanize
import bleach  # type: ignore[import-untyped]
from datetime import datetime, timedelta
from typing import Optional, Union
from collections.abc import Iterable
from collections.abc import Iterator
from jinja2 import Environment


def widget_uuid(length: int = 8) -> str:
    """Generate a unique widget ID."""
    unique_id = f"widget_{uuid.uuid4()}"
    return unique_id.replace("-", "")


def datetime_minutes(dt: timedelta) -> int:
    """Convert datetime to minutes."""
    return (dt.days * 24 * 60) + (dt.seconds // 60)


def human_datetime(value: datetime, relative: bool = True) -> str:
    """Format datetime in human readable format."""
    if relative:
        return humanize.naturaltime(value)
    else:
        return "{dt:%b} {dt:%-d}, {dt:%Y} {dt:%-I}:{dt:%M} {ampm}".format(
            dt=value, ampm=value.strftime("%p").lower()
        )


def human_timedelta(td: timedelta) -> str:
    """Format timedelta in human readable format."""
    return humanize.naturaldelta(td)


def sorteditems(dictionary: dict) -> list:
    """Sort dictionary items by key."""
    return sorted(dictionary.items())


def batch(iterable: Iterable, count: int) -> Iterator[list]:
    """Batch items into groups of specified count."""
    result = []
    for item in iterable:
        result.append(item)
        if len(result) == count:
            yield result
            result = []
    if result:
        yield result


def dict_batch(d: dict, count: int) -> Iterator[list]:
    """Batch dictionary items into groups."""
    yield from batch(d.items(), count)


def remove_empty(dictionary: dict) -> dict:
    """Remove empty values from dictionary."""
    return {k: v for k, v in dictionary.items() if v}


def by_key(dictionary: dict, key: str) -> str:
    """Get dictionary value by key."""
    return dictionary.get(key, "")


def by_nested_key(dictionary: dict, key: str) -> Optional[str]:
    """Get nested dictionary value by space-separated key."""
    split_key = key.split()
    src = dictionary.get(split_key[0], None)
    if src:
        return src.get(split_key[1], "")
    else:
        return None


def is_list(item: object) -> bool:
    """Check if item is a list."""
    return isinstance(item, list)


def typeof(item: object) -> type:
    """Get type of item."""
    return type(item)


def safe_intcomma(value: Union[str, int]) -> str:
    """Format integer with commas, safely handling non-integers."""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def hash_function(value: str, salt: str = "") -> str:
    """Hash a value with optional salt."""
    salted = f"{salt}{value}"
    return hashlib.sha512(salted.encode()).hexdigest()


def startswith(s: str, s2: str) -> bool:
    """Check if string starts with substring."""
    return str(s).startswith(str(s2))


def getattribute(obj: object, key: str) -> object:
    """Get attribute from object."""
    return getattr(obj, key, "")


def superslug(s: str) -> str:
    """Create a super slug from string."""
    s = str(s).replace("-", "_").replace(" ", "_")
    s = re.sub(r"\W", "", s)
    return s


def sformat(s: str, value: object) -> str:
    """Format string with value."""
    return str(s) % value


def jslist(obj: list) -> str:
    """Convert list to JavaScript array string."""
    return "[" + ",".join([f"'{s}'" for s in obj]) + "]"


def to_json(obj: object) -> str:
    """Convert object to JSON string."""
    return json.dumps(obj)


def absval(obj: Union[int, float]) -> Union[int, float]:
    """Get absolute value."""
    return abs(obj)


def commasplit(string: str, index: int) -> str:
    """Split string by comma and get item at index."""
    return str(string).split(",")[index]


def slashsplit(string: str) -> list[str]:
    """Split string by slash."""
    return str(string).split("/")


def strip_tenant_id(dictionary: dict, key: str) -> str:
    """Strip tenant ID from dictionary value."""
    x = dictionary.get(key, "")
    if len(x):
        return str(x).split("_")[0]
    else:
        return ""


def bleach_clean(value: str, **kwargs: object) -> str:
    """Clean HTML using bleach."""
    return bleach.clean(value, **kwargs)


# Global functions for templates
JINJA2_GLOBALS = {
    "widget_uuid": widget_uuid,
}

# Filters for templates
JINJA2_FILTERS = {
    "datetime_minutes": datetime_minutes,
    "human_datetime": human_datetime,
    "human_timedelta": human_timedelta,
    "sorteditems": sorteditems,
    "batch": batch,
    "dict_batch": dict_batch,
    "remove_empty": remove_empty,
    "by_key": by_key,
    "by_nested_key": by_nested_key,
    "is_list": is_list,
    "typeof": typeof,
    "safe_intcomma": safe_intcomma,
    "startswith": startswith,
    "getattribute": getattribute,
    "superslug": superslug,
    "sformat": sformat,
    "jslist": jslist,
    "to_json": to_json,
    "absval": absval,
    "commasplit": commasplit,
    "slashsplit": slashsplit,
    "strip_tenant_id": strip_tenant_id,
    "bleach": bleach_clean,
}


def setup_jinja_env(env: Environment) -> Environment:
    """Setup Jinja2 environment with custom filters and globals."""
    env.filters.update(JINJA2_FILTERS)
    env.globals.update(JINJA2_GLOBALS)
    return env
