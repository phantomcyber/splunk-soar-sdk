from soar_sdk.compat import remove_when_soar_newer_than

remove_when_soar_newer_than(
    "6.4.0",
    "This boilerplate is needed to support webhooks in older SOAR versions. This file can be cleared out now",
)

from . import app

__ALL__ = [app]
