from collections.abc import Sequence
from typing import (
    NewType,
    Protocol,
)

SpecForkName = NewType("SpecForkName", str)
PresetBaseName = NewType("PresetBaseName", str)
SpecForks = Sequence[SpecForkName]


class Configuration(Protocol):
    PRESET_BASE: str


class Spec(Protocol):
    fork: str
    config: Configuration
