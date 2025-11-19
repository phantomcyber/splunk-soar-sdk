"""Test file with intentional failures to demonstrate auto-fix."""


def test_missing_package():
    """This test will fail due to missing package - auto-fixable."""
    import yaml
    assert yaml is not None


def test_passing():
    """This test should pass."""
    assert 2 + 2 == 4
