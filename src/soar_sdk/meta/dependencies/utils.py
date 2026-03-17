def normalize_package_name(name: str) -> str:
    """Normalize the package name by converting it to lowercase and replacing hyphens with underscores.

    Python treats package names as case-insensitive and doesn't differentiate between hyphens and
    underscores, so "my_awesome_package" is equivalent to "mY_aWeSoMe-pAcKaGe".
    """
    return name.lower().replace("-", "_")


def normalize_package_set(packages: set[str]) -> set[str]:
    """Normalizes a whole set of package names (converting uppercase to lowercase and hyphens to underscores)."""
    return set([normalize_package_name(p) for p in packages])
