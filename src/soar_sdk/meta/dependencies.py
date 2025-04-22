from typing import Optional
from pydantic import BaseModel, Field, PrivateAttr

# from functools import cached_property
# TODO: when we upgrade to pydantic 2, we can replace our properties with cached properties


class DependencyWheel(BaseModel):
    module: str
    input_file: str
    input_file_aarch64: Optional[str] = None
    _wheel: "UvWheel" = PrivateAttr()
    _wheel_aarch64: Optional["UvWheel"] = PrivateAttr()


class DependencyList(BaseModel):
    wheels: list[DependencyWheel] = Field(default_factory=list)


class UvWheel(BaseModel):
    url: str
    hash: str
    size: int

    # The wheel file name is specified by PEP427. It's either a 5- or 6-tuple:
    # {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
    # We can parse this to determine which configurations it supports.
    @property
    def basename(self) -> str:
        filename = self.url.split("/")[-1]
        return filename.removesuffix(".whl")

    @property
    def distribution(self) -> str:
        return self.basename.split("-")[0]

    @property
    def version(self) -> str:
        return self.basename.split("-")[1]

    @property
    def build_tag(self) -> Optional[str]:
        split = self.basename.split("-")
        if len(split) == 6:
            return split[2]
        return None

    @property
    def python_tags(self) -> list[str]:
        return self.basename.split("-")[-3].split(".")

    @property
    def abi_tags(self) -> list[str]:
        return self.basename.split("-")[-2].split(".")

    @property
    def platform_tags(self) -> list[str]:
        return self.basename.split("-")[-1].split(".")


class UvDependency(BaseModel):
    name: str


class UvPackage(BaseModel):
    name: str
    version: str
    dependencies: list[UvDependency] = []
    wheels: list[UvWheel] = []

    def _find_wheel(
        self,
        abi_precedence: list[str],
        python_precedence: list[str],
        platform_precedence: list[str],
    ) -> UvWheel:
        """
        Search the list of wheels in uv.lock for the given package and return the first one that matches the given constraints.
        Constraints are evaluated in the order: ABI tag -> Python tag -> platform tag.
        If multiple wheels match a given triple, the first one in uv.lock is returned.
        If no wheel satisfies the given constraints, a FileNotFoundError is raised.
        """
        for abi in abi_precedence:
            abi_wheels = [wheel for wheel in self.wheels if abi in wheel.abi_tags]
            for python in python_precedence:
                python_wheels = [
                    wheel for wheel in abi_wheels if python in wheel.python_tags
                ]
                for platform in platform_precedence:
                    platform_wheels = [
                        wheel
                        for wheel in python_wheels
                        if platform in wheel.platform_tags
                    ]
                    if len(platform_wheels) > 0:
                        return platform_wheels[0]

        raise FileNotFoundError(
            f"Could not find a suitable wheel for {self.name=}, {self.version=}, {abi_precedence=}, {python_precedence=}, {platform_precedence=}"
        )

    _manylinux_precedence = [
        "_2_28",  # glibc 2.28, latest stable version, supports Ubuntu 18.10+ and RHEL/Oracle 8+
        "_2_17",  # glibc 2.17, LTS-ish, supports Ubuntu 13.10+ and RHEL/Oracle 7+
        "2014",  # Synonym for _2_17
    ]
    platform_precedence_x86_64 = [
        *[f"manylinux{version}_x86_64" for version in _manylinux_precedence],
        "any",
    ]
    platform_precedence_aarch64 = [
        *[f"manylinux{version}_aarch64" for version in _manylinux_precedence],
        "any",
    ]

    def _resolve(
        self, dir_name: str, abi_precedence: list[str], python_precedence: list[str]
    ) -> DependencyWheel:
        wheel_x86_64 = self._find_wheel(
            abi_precedence, python_precedence, self.platform_precedence_x86_64
        )

        wheel = DependencyWheel(
            module=self.name,
            input_file=f"wheels/{dir_name}/{wheel_x86_64.basename}.whl",
            _wheel=wheel_x86_64,
        )

        try:
            wheel_aarch64 = self._find_wheel(
                abi_precedence, python_precedence, self.platform_precedence_aarch64
            )
            wheel.input_file_aarch64 = f"wheels/{dir_name}/{wheel_aarch64.basename}.whl"
            wheel._wheel_aarch64 = wheel_aarch64
        except FileNotFoundError:
            print(
                f"Warning: Could not find a suitable {dir_name} / aarch64 wheel for {self.name=}, {self.version=} -- the built package might not work on ARM systems"
            )

        return wheel

    def resolve_py39(self) -> DependencyWheel:
        return self._resolve(
            dir_name="python39",
            abi_precedence=[
                "cp39",  # Python 3.9-specific ABI
                "abi3",  # Python 3 stable ABI
                "none",  # Source wheels -- no ABI
            ],
            python_precedence=[
                "cp39",  # Binary wheel for Python 3.9
                "pp39",  # Source wheel for Python 3.9
                "py3",  # Source wheel for any Python 3.x
            ],
        )

    def resolve_py313(self) -> DependencyWheel:
        return self._resolve(
            dir_name="python313",
            abi_precedence=[
                "cp313",  # Python 3.13-specific ABI
                "abi3",  # Python 3 stable ABI
                "none",  # Source wheels -- no ABI
            ],
            python_precedence=[
                "cp313",  # Binary wheel for Python 3.13
                "pp313",  # Source wheel for Python 3.13
                "py3",  # Source wheel for any Python 3.x
            ],
        )


class UvLock(BaseModel):
    package: list[UvPackage]

    def get_package_entry(self, name: str) -> UvPackage:
        return [p for p in self.package if p.name == name][0]

    def build_package_list(self, root_package_name: str) -> list[UvPackage]:
        packages = {root_package_name: self.get_package_entry(root_package_name)}

        new_packages_added = True
        while new_packages_added:
            new_packages_added = False

            scan_pass = list(packages.values())
            for package in scan_pass:
                for dependency in package.dependencies:
                    name = dependency.name
                    if name not in packages:
                        packages[name] = self.get_package_entry(name)
                        new_packages_added = True

        # Exclude the connector itself from the list of dependencies
        del packages[root_package_name]

        # TODO: prune wheels that are provided with the platform (bs4, requests/urllib, etc.)
        # TODO: denylist for wheels that shouldn't be used in connectors (simplejson, django, etc.)

        return sorted(packages.values(), key=lambda p: p.name)
