from .typing import SpecForkName, PresetBaseName


#
# SpecForkName
#
# Some of the Spec module functionality is exposed here to deal with phase-specific changes.
PHASE0 = SpecForkName('phase0')
ALTAIR = SpecForkName('altair')
BELLATRIX = SpecForkName('bellatrix')
CAPELLA = SpecForkName('capella')

# Experimental phases (not included in default "ALL_PHASES"):
SHARDING = SpecForkName('sharding')
CUSTODY_GAME = SpecForkName('custody_game')
DAS = SpecForkName('das')
EIP4844 = SpecForkName('eip4844')

# The forks that pytest can run with.
ALL_PHASES = (
    # Formal forks
    PHASE0, ALTAIR, BELLATRIX, CAPELLA,
    # Experimental patches
    EIP4844,
)
# The forks that output to the test vectors.
TESTGEN_FORKS = (PHASE0, ALTAIR, BELLATRIX)

FORKS_BEFORE_ALTAIR = (PHASE0,)
FORKS_BEFORE_BELLATRIX = (PHASE0, ALTAIR)
FORKS_BEFORE_CAPELLA = (PHASE0, ALTAIR, BELLATRIX)
ALL_FORK_UPGRADES = {
    # pre_fork_name: post_fork_name
    PHASE0: ALTAIR,
    ALTAIR: BELLATRIX,
    BELLATRIX: CAPELLA,
}
ALL_PRE_POST_FORKS = ALL_FORK_UPGRADES.items()
AFTER_BELLATRIX_UPGRADES = {key: value for key, value in ALL_FORK_UPGRADES.items() if key not in FORKS_BEFORE_ALTAIR}
AFTER_BELLATRIX_PRE_POST_FORKS = AFTER_BELLATRIX_UPGRADES.items()

#
# Config
#
MAINNET = PresetBaseName('mainnet')
MINIMAL = PresetBaseName('minimal')

ALL_PRESETS = (MINIMAL, MAINNET)


#
# Number
#
MAX_UINT_64 = 2**64 - 1
