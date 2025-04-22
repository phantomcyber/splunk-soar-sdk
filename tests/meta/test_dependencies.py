from soar_sdk.meta.dependencies import UvWheel, UvPackage

from typing import TypedDict, Optional


def test_parse_uvwheel():
    class UvWheelTest(TypedDict):
        wheel: UvWheel
        basename: str
        distribution: str
        version: str
        build_tag: Optional[str]
        python_tags: list[str]
        abi_tags: list[str]
        platform_tags: list[str]

    tests = [
        UvWheelTest(
            wheel=UvWheel(
                url="https://files.pythonhosted.org/packages/38/fc/bce832fd4fd99766c04d1ee0eead6b0ec6486fb100ae5e74c1d91292b982/certifi-2025.1.31-py3-none-any.whl",
                hash="sha256:ca78db4565a652026a4db2bcdf68f2fb589ea80d0be70e03929ed730746b84fe",
                size=166393,
            ),
            basename="certifi-2025.1.31-py3-none-any",
            distribution="certifi",
            version="2025.1.31",
            build_tag=None,
            python_tags=["py3"],
            abi_tags=["none"],
            platform_tags=["any"],
        ),
        UvWheelTest(
            wheel=UvWheel(
                url="https://example.com/fictional_package-2.2.2-32a-py3-none-any.whl",
                hash="sha256:asdf",
                size=9999,
            ),
            basename="fictional_package-2.2.2-32a-py3-none-any",
            distribution="fictional_package",
            version="2.2.2",
            build_tag="32a",
            python_tags=["py3"],
            abi_tags=["none"],
            platform_tags=["any"],
        ),
    ]

    for test in tests:
        assert test["wheel"].basename == test["basename"]
        assert test["wheel"].distribution == test["distribution"]
        assert test["wheel"].version == test["version"]
        assert test["wheel"].build_tag == test["build_tag"]
        assert test["wheel"].python_tags == test["python_tags"]
        assert test["wheel"].abi_tags == test["abi_tags"]
        assert test["wheel"].platform_tags == test["platform_tags"]


class TestUvPackage:
    def test_find_wheel(self):
        package = UvPackage(
            name="certifi",
            version="2025.1.31",
            dependencies=[],
            wheels=[
                UvWheel(
                    url="https://files.pythonhosted.org/packages/38/fc/bce832fd4fd99766c04d1ee0eead6b0ec6486fb100ae5e74c1d91292b982/certifi-2025.1.31-py3-none-any.whl",
                    hash="sha256:ca78db4565a652026a4db2bcdf68f2fb589ea80d0be70e03929ed730746b84fe",
                    size=166393,
                )
            ],
        )
        wheel = package._find_wheel(
            abi_precedence=["cp39", "abi3", "none"],
            python_precedence=["cp39", "pp39", "py3"],
            platform_precedence=[
                "manylinux_2_28_x86_64",
                "manylinux_2_17_x86_64",
                "manylinux2014_x86_64",
                "any",
            ],
        )
        assert wheel.basename == "certifi-2025.1.31-py3-none-any"

    def test_resolve_no_aarch64_available(self):
        package = UvPackage(
            name="mypy",
            version="1.2.0",
            wheels=[
                UvWheel(
                    url="https://files.pythonhosted.org/packages/3d/42/abf8568dbbe9e207ac90d650164aac43ed9c40fbae0d5f87d842d62ec485/mypy-1.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
                    hash="sha256:023fe9e618182ca6317ae89833ba422c411469156b690fde6a315ad10695a521",
                    size=12190233,
                )
            ],
        )
        wheel = package.resolve_py39()

        assert (
            wheel.input_file
            == "wheels/python39/mypy-1.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
        )
        assert wheel.input_file_aarch64 is None
