import logging
from unittest import mock
from soar_sdk.compat import remove_when_soar_newer_than
from soar_sdk.meta.dependencies import (
    UvSourceDistribution,
    UvWheel,
    UvPackage,
    UvLock,
    DependencyWheel,
    UvDependency,
)

from typing import Optional

from typing_extensions import TypedDict

remove_when_soar_newer_than(
    "7.0.0", "NotRequired from typing_extensions is in typing in Python 3.11+"
)

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

    def test_resolve_sdist(self):
        package = UvPackage(
            name="splunk-sdk",
            version="2.1.0",
            sdist=UvSourceDistribution(
                url="https://example.com/splunk-sdk-2.1.0.tar.gz",
                hash="sha256:deadbeef",
                size=123456,
            ),
        )

        wheel = package.resolve_py39()
        assert wheel.sdist is not None

    def test_resolve_forbidden_sdist_fails(self):
        package = UvPackage(
            name="foobar",
            version="2.1.0",
            sdist=UvSourceDistribution(
                url="https://example.com/foobar-0.1.0.tar.gz",
                hash="sha256:deadbeef",
                size=123456,
            ),
        )

        with pytest.raises(
            FileNotFoundError,
            match="Could not find a suitable x86_64 wheel or source distribution",
        ):
            package.resolve_py39()

    def test_resolve_sdist_warns_once(self):
        package = UvPackage(
            name="splunk-sdk",
            version="2.1.0",
            sdist=UvSourceDistribution(
                url="https://example.com/splunk-sdk-2.1.0.tar.gz",
                hash="sha256:deadbeef",
                size=123456,
            ),
        )

        logger = logging.getLogger("soar_sdk.meta.dependencies")
        with mock.patch.object(logger, "warning") as mock_warn:
            package.resolve_py39()
            package.resolve_py313()

        mock_warn.assert_called_once()


class TestUvLock:
    def test_missing_package_entry(self):
        lock = UvLock(package=[])

        with pytest.raises(LookupError, match="No package 'requests' found in uv.lock"):
            lock.get_package_entry("requests")

    def test_build_package_list(self, fake_uv_lockfile: UvLock):
        packages = fake_uv_lockfile.build_package_list("example-app")
        assert len(packages) == 1
        assert packages[0].name == "fakepkg"

    def test_build_package_list_with_equivalent_name(self, fake_uv_lockfile: UvLock):
        packages = fake_uv_lockfile.build_package_list("eXaMpLe_ApP")
        assert len(packages) == 1
        assert packages[0].name == "fakepkg"

    def test_rejected_dependency(
        self, wheel_resp_mock, fake_wheel: UvWheel, fake_uv_lockfile: UvLock
    ):
        fake_uv_lockfile.package.append(
            UvPackage(name="simplejson", version="3.20.1", wheels=[fake_wheel])
        )
        fake_uv_lockfile.package[0].dependencies.append(UvDependency(name="simplejson"))

        with pytest.raises(
            ValueError,
            match="The 'simplejson' package is not allowed in a SOAR connector. Please remove it from your app's dependencies.",
        ):
            fake_uv_lockfile.build_package_list("example-app")


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

    @pytest.mark.asyncio
    async def test_collect_sdist(
        self, sdist_resp_mock, fake_sdist: UvSourceDistribution
    ):
        wheel = DependencyWheel(module="splunk_sdk", sdist=fake_sdist)

        results = []
        async for item in wheel.collect_wheels():
            results.append(item)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_collect_wheel_with_no_sources(self):
        wheel = DependencyWheel(module="broken-pkg")

        with pytest.raises(
            ValueError, match="Could not find a suitable wheel or source distribution"
        ):
            async for _ in wheel.collect_wheels():
                pass


class TestUvSourceDistribution:
    @pytest.mark.asyncio
    async def test_fetch_and_build_sdist(
        self,
        sdist_resp_mock,
        fake_sdist: UvSourceDistribution,
    ):
        wheel_name, wheel = await fake_sdist.fetch_and_build()

        assert wheel_name == "splunk_sdk-2.1.0-py3-none-any.whl"
        assert len(wheel) > 0

        assert sdist_resp_mock.called

    @pytest.mark.asyncio
    async def test_fetch_and_build_sdist_hash_mismatch(
        self,
        sdist_resp_mock,
        fake_sdist: UvSourceDistribution,
    ):
        fake_sdist.hash = "sha256:deadbeef"

        with pytest.raises(ValueError, match="did not match the expected checksum"):
            await fake_sdist.fetch_and_build()
