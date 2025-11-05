import os
import sys
import json
import argparse
from enum import Enum
from datetime import date
from dataclasses import dataclass
from abc import ABC, abstractmethod
from collections import defaultdict

import requests
from packaging.version import Version


CPYTHON_INDEX = (
    "https://raw.githubusercontent.com/actions/python-versions"
    "/refs/heads/main/versions-manifest.json"
)
PYPY_INDEX = "https://downloads.python.org/pypy/versions.json"
EOL_INDEX = "https://endoflife.date/api/python.json"


def _version(v: str) -> Version | None:
    return None if v == "auto" else Version(v)


parser = argparse.ArgumentParser()
parser.add_argument("min_version", type=_version)
parser.add_argument("max_version", type=_version)
parser.add_argument("include_pre_releases", type=json.loads)
parser.add_argument("include_freethreaded", type=json.loads)
parser.add_argument("implementations", type=json.loads)
parser.add_argument("check_platform", type=json.loads)


class BaseEntry(ABC):
    def __init__(self, data: dict) -> None:
        self.data = data
        self._version = self._extract_version()
        self.version = Version(self._version)

    @abstractmethod
    def _extract_version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def string(self, suffix: str) -> str:
        raise NotImplementedError

    def _simple_version(self, suffix: str) -> str:
        version = f"{self.version.major}.{self.version.minor}{suffix}"
        if self.version.is_prerelease:
            version += "-dev"
        return version


class CPythonEntry(BaseEntry):
    def _extract_version(self) -> str:
        return self.data["version"]

    def string(self, suffix: str) -> str:
        if self.version.is_prerelease:
            return self._simple_version(suffix)
        return self._version + suffix


class PyPyEntry(CPythonEntry):
    def _extract_version(self) -> str:
        return self.data["python_version"]

    def string(self, suffix: str) -> str:
        return f"pypy-{self._simple_version(suffix)}"


def _invert_dict(d: dict) -> dict:
    result = {}
    for k, v in d.items():
        for i in v:
            result[i] = k
    return result


KNOWN_IMPLEMENTATIONS = {
    "cpython": (CPYTHON_INDEX, CPythonEntry),
    "pypy": (PYPY_INDEX, PyPyEntry),
}


OperatingSystem = Enum("OperatingSystem", ["LINUX", "WINDOWS", "MACOS"])
Architecture = Enum("Architecture", ["X86", "X64", "ARM64"])

KNOWN_OS_NAMES = _invert_dict(
    {
        OperatingSystem.LINUX: ["linux"],
        OperatingSystem.WINDOWS: ["windows", "win32", "win64"],
        OperatingSystem.MACOS: ["macos", "darwin"],
    }
)
KNOWN_ARCH_NAMES = _invert_dict(
    {
        Architecture.X86: ["x86", "i686"],
        Architecture.X64: ["x64"],
        Architecture.ARM64: ["aarch64", "arm64"],
    }
)
FREETHREADED_SUFFIX = "-freethreaded"


def _get_os(name: str) -> OperatingSystem | None:
    return KNOWN_OS_NAMES.get(name.lower())


def _get_arch(name: str) -> Architecture | None:
    return KNOWN_ARCH_NAMES.get(name.lower().removesuffix(FREETHREADED_SUFFIX))


@dataclass
class EntryProcessor:
    min_version: Version
    max_version: Version | None
    include_pre_releases: bool
    include_freethreaded: bool
    target_os: OperatingSystem | None
    target_arch: Architecture | None

    def process(self, entries: list[BaseEntry]) -> list[str]:
        versions = defaultdict(list)

        for entry in entries:
            if entry.version < self.min_version:
                continue
            if self.max_version and entry.version >= self.max_version:
                continue
            if not self.include_pre_releases and entry.version.is_prerelease:
                continue
            files = entry.data["files"]
            if self.target_os:
                files = filter(
                    lambda f: _get_os(f["platform"]) == self.target_os, files
                )
            if self.target_arch:
                files = filter(
                    lambda f: _get_arch(f["arch"]) == self.target_arch, files
                )
            files = list(files)
            files_freethreaded = [
                f for f in files if f["arch"].endswith(FREETHREADED_SUFFIX)
            ]
            if len(files_freethreaded) < len(files):
                versions[
                    (entry.version.major, entry.version.minor, "")
                ].append(entry)
            if self.include_freethreaded and files_freethreaded:
                versions[
                    (entry.version.major, entry.version.minor, "t")
                ].append(entry)

        return [
            max(releases, key=lambda r: r.version).string(suffix)
            for (major, minor, suffix), releases in versions.items()
        ]


def fetch_auto_min() -> Version:
    return min(
        Version(entry["cycle"])
        for entry in requests.get(EOL_INDEX).json()
        if date.fromisoformat(entry["eol"]) > date.today()
    )


def fetch_versions(
    *,
    min_version: Version | None,
    max_version: Version | None,
    include_pre_releases: bool,
    include_freethreaded: bool,
    implementations: list[str],
    target_os: OperatingSystem | None,
    target_arch: Architecture | None,
) -> list[str]:
    if min_version is None:
        min_version = fetch_auto_min()

    versions = []
    version_processor = EntryProcessor(
        min_version,
        max_version,
        include_pre_releases,
        include_freethreaded,
        target_os,
        target_arch,
    )

    for impl in implementations:
        if impl not in KNOWN_IMPLEMENTATIONS:
            raise ValueError(f"unsupported implementation: {impl}")
        url, klass = KNOWN_IMPLEMENTATIONS[impl]
        data = [klass(e) for e in requests.get(url).json()]
        versions.extend(version_processor.process(data))

    return versions


def main(args: list[str]) -> None:
    args = vars(parser.parse_args(args))

    assert isinstance(
        args["implementations"], list
    ), "implementations must be a list"
    for arg in [
        "include_pre_releases",
        "include_freethreaded",
        "check_platform",
    ]:
        assert isinstance(args[arg], bool), f"{arg} must be a boolean"
    args["implementations"] = [i.lower() for i in args["implementations"]]
    if args.pop("check_platform"):
        args["target_os"] = _get_os(os.getenv("RUNNER_OS"))
        args["target_arch"] = _get_arch(os.getenv("RUNNER_ARCH"))
    else:
        args["target_os"] = None
        args["target_arch"] = None

    print(json.dumps(fetch_versions(**args)))


if __name__ == "__main__":
    main(sys.argv[1:])
