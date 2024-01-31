from __future__ import annotations

import re


class Version:
    revisions = [None, "rc", "betta", "alpha"]

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        revision: str = None,
        revision_number: int = None,
    ):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.revision = revision
        self.revision_number = revision_number
        if revision not in self.revisions:
            raise ValueError(
                f"Unknown revision `{revision}`. it can be {self.revisions}"
            )

    @classmethod
    def from_str(cls, string_version: str) -> Version:
        if match := re.fullmatch(
            r"(\d+).(\d+).(\d+)(-(\S+).(\d+))?",
            string_version,
        ):
            return Version(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                match.group(5),
                int(match.group(6)),
            )
        raise ValueError(f"Can`t parse version from string: {string_version}")

    def to_str(self, revision: bool = True) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if revision and self.revision:
            version += f"-{self.revision}.{self.revision_number}"
        return version

    def __eq__(self, other: Version):
        return str(self) == str(other)

    def __gt__(self, other: Version):
        if self.to_str(False) != other.to_str(False):
            return self.to_str(False) > other.to_str(False)
        self_revision_index = Version.revisions.index(self.revision)
        other_revision_index = Version.revisions.index(other.revision)
        if self_revision_index != other_revision_index:
            return self_revision_index < other_revision_index
        return self.revision_number > other.revision_number

    def __repr__(self):
        return self.to_str()

    __str__ = __repr__
