from soar_sdk.meta.dependencies import (
    UvWheel,
    UvPackage,
    UvLock,
    DependencyWheel,
    UvDependency,
)

from typing import TypedDict, Optional

import pytest


class TestUvWheel:
    def test_parse_uvwheel(self):
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
                    url="https://notarealurl.com/certifi-2025.1.31-py3-none-any.whl",
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

    @pytest.mark.asyncio
    async def test_fetch_wheel(self, wheel_resp_mock, fake_wheel: UvWheel):
        wheel_bytes = await fake_wheel.fetch()
        assert len(wheel_bytes) == fake_wheel.size
        assert wheel_resp_mock.call_count == 1

    @pytest.mark.asyncio
    async def test_fetch_wheel_hash_mismatch(
        self, wheel_resp_mock, fake_wheel: UvWheel
    ):
        fake_wheel.hash = "sha256:deadbeef"
        with pytest.raises(
            ValueError,
            match=r"Retrieved wheel.+did not match the expected checksum",
        ):
            await fake_wheel.fetch()

        assert wheel_resp_mock.call_count == 1


class TestUvPackage:
    def test_find_wheel(self):
        package = UvPackage(
            name="certifi",
            version="2025.1.31",
            dependencies=[],
            wheels=[
                UvWheel(
                    url="https://notarealurl.com/certifi-2025.1.31-py3-none-any.whl",
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
                    url="https://notarealurl.com/mypy-1.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
                    hash="sha256:023fe9e618182ca6317ae89833ba422c411469156b690fde6a315ad10695a521",
                    size=12190233,
                )
            ],
        )
        wheel = package.resolve_py39()
        wheel.add_platform_prefix("python39")

        assert (
            wheel.input_file
            == "wheels/python39/mypy-1.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
        )
        assert wheel.input_file_aarch64 is None


class TestUvLock:
    def test_missing_package_entry(self):
        lock = UvLock(package=[])

        with pytest.raises(LookupError, match="No package 'requests' found in uv.lock"):
            lock.get_package_entry("requests")

    def test_rejected_dependency(self, wheel_resp_mock, fake_wheel: UvWheel):
        lock = UvLock(
            package=[
                UvPackage(
                    name="example-app",
                    version="1.0.0",
                    dependencies=[
                        UvDependency(name="fakepkg"),
                        UvDependency(name="simplejson"),
                    ],
                ),
                UvPackage(name="fakepkg", version="1.0.0", wheels=[fake_wheel]),
                UvPackage(name="simplejson", version="3.20.1", wheels=[fake_wheel]),
            ]
        )

        with pytest.raises(
            ValueError,
            match="The 'simplejson' package is not allowed in a SOAR connector. Please remove it from your app's dependencies.",
        ):
            lock.build_package_list("example-app")


class TestDependencyWheel:
    @pytest.mark.asyncio
    async def test_collect_no_aarch64_wheel(self, wheel_resp_mock, fake_wheel: UvWheel):
        wheel = DependencyWheel(
            module="mypy",
            input_file="wheels/python39/mypy-1.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
            wheel=fake_wheel,
        )

        results = []
        async for item in wheel.collect_wheels():
            results.append(item)
        assert len(results) == 1

    def test_hash(self, fake_wheel: UvWheel):
        wheel1 = DependencyWheel(
            module="mypy",
            input_file="wheels/python39/mypy-1.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
            wheel=fake_wheel,
        )
        wheel2 = DependencyWheel(
            module="mypy",
            input_file="wheels/python39/mypy-1.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
            wheel=fake_wheel,
        )

        assert hash(wheel1) == hash(wheel2)
