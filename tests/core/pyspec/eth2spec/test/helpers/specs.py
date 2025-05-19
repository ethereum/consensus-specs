from typing import (
    Dict,
)

from .constants import (
    ALL_PHASES,
    EIP7441,
    MAINNET,
    MINIMAL,
)
from .typing import (
    PresetBaseName,
    Spec,
    SpecForkName,
)

# NOTE: special case like `ALLOWED_TEST_RUNNER_FORKS`
ALL_EXECUTABLE_SPEC_NAMES = ALL_PHASES + (EIP7441,)

# import the spec for each fork and preset
for fork in ALL_EXECUTABLE_SPEC_NAMES:
    exec(
        f"from eth2spec.{fork} import mainnet as spec_{fork}_mainnet, minimal as spec_{fork}_minimal"
    )

# this is the only output of this file
spec_targets: Dict[PresetBaseName, Dict[SpecForkName, Spec]] = {
    MINIMAL: {fork: eval(f"spec_{fork}_minimal") for fork in ALL_EXECUTABLE_SPEC_NAMES},
    MAINNET: {fork: eval(f"spec_{fork}_mainnet") for fork in ALL_EXECUTABLE_SPEC_NAMES},
}
