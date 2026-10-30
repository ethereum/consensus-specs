from .constants import (
    ALL_PHASES,
    MAINNET,
    MINIMAL,
)
from .execution_engine import get_test_execution_engine
from .forks import is_post_bellatrix
from .typing import (
    PresetBaseName,
    Spec,
    SpecForkName,
)

ALL_EXECUTABLE_SPEC_NAMES = ALL_PHASES

# import the spec for each fork and preset
for fork in ALL_EXECUTABLE_SPEC_NAMES:
    exec(
        f"from eth_consensus_specs.{fork} import mainnet as spec_{fork}_mainnet, minimal as spec_{fork}_minimal"
    )

# this is the only output of this file
spec_targets: dict[PresetBaseName, dict[SpecForkName, Spec]] = {
    MINIMAL: {fork: eval(f"spec_{fork}_minimal") for fork in ALL_EXECUTABLE_SPEC_NAMES},
    MAINNET: {fork: eval(f"spec_{fork}_mainnet") for fork in ALL_EXECUTABLE_SPEC_NAMES},
}

for targets in spec_targets.values():
    for spec in targets.values():
        if is_post_bellatrix(spec):
            spec.EXECUTION_ENGINE = get_test_execution_engine(spec)
