from soar_sdk.compat import remove_when_soar_newer_than
from soar_sdk.meta.dependencies.utils import normalize_package_set

# These dependencies are provided by the Python runner,
# so the SDK will not include wheels for them when building a package.
DEPENDENCIES_TO_SKIP = normalize_package_set(
    {
        # "splunk-soar-sdk",
        # List from https://docs.splunk.com/Documentation/SOAR/current/DevelopApps/FAQ
        "beautifulsoup4",
        "soupsieve",
        "parse",
        "python_dateutil",
        "six",
        "requests",
        "certifi",
        "charset_normalizer",
        "idna",
        "urllib3",
        "sh",
        "xmltodict",
    }
)

# These dependencies should never be included with a connector,
# so the SDK will raise an error if it finds them in the lock.
DEPENDENCIES_TO_REJECT = normalize_package_set(
    {
        "simplejson",  # no longer needed, please use the built-in `json` module instead
        "django",  # apps should never depend on Django
    }
)

# These dependencies can be built from a source distribution if no wheel is available.
# We should keep this list very short, pressure the maintainers of these packages to provide wheels,
# and remove packages from the list once they're available as wheels.
remove_when_soar_newer_than(
    "7.0.0",
    "If the Splunk SDK is available as a wheel now, remove it, and remove all of the code for building wheels from source.",
)
DEPENDENCIES_TO_BUILD = normalize_package_set(
    {
        "splunk_sdk",  # https://github.com/splunk/splunk-sdk-python/pull/656,
        "splunk_soar_sdk",  # Useful to build from source when developing the SDK
        "red_black_tree_mod",  # Required for email parsing
    }
)
