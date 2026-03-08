from importlib import import_module

from .constants import (
    ALL_PHASES,
    MAINNET,
    MINIMAL,
)
from .typing import (
    PresetBaseName,
    Spec,
    SpecForkName,
)

ALL_EXECUTABLE_SPEC_NAMES = ALL_PHASES


class _LazySpecDict(dict):
    """Dict that lazily imports spec modules on first access."""

    def __init__(self, preset: str):
        super().__init__()
        self._preset = preset
        # Pre-populate keys so iteration/membership checks work without importing
        for fork in ALL_EXECUTABLE_SPEC_NAMES:
            dict.__setitem__(self, fork, None)

    def __getitem__(self, fork: str) -> Spec:
        value = dict.__getitem__(self, fork)
        if value is None:
            mod = import_module(f"eth_consensus_specs.{fork}.{self._preset}")
            dict.__setitem__(self, fork, mod)
            return mod
        return value

    def get(self, fork, default=None):
        if fork in self:
            return self[fork]
        return default

    def values(self):
        # Trigger lazy loading for all modules before returning values.
        # Called by _apply_ckzg to patch all spec modules.
        for fork in list(self.keys()):
            self[fork]
        return dict.values(self)


spec_targets: dict[PresetBaseName, dict[SpecForkName, Spec]] = {
    MINIMAL: _LazySpecDict("minimal"),
    MAINNET: _LazySpecDict("mainnet"),
}
