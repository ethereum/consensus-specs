from .typing import SpecForkName, PresetBaseName


#
# SpecForkName
#
# Some of the Spec module functionality is exposed here to deal with phase-specific changes.
PHASE0 = SpecForkName('phase0')
ALTAIR = SpecForkName('altair')
MERGE = SpecForkName('merge')

# Experimental phases (not included in default "ALL_PHASES"):
SHARDING = SpecForkName('sharding')
CUSTODY_GAME = SpecForkName('custody_game')
DAS = SpecForkName('das')

# The forks that pytest runs with.
ALL_PHASES = (PHASE0, ALTAIR, MERGE)
# The forks that output to the test vectors.
TESTGEN_FORKS = (PHASE0, ALTAIR, MERGE)

FORKS_BEFORE_ALTAIR = (PHASE0,)
FORKS_BEFORE_MERGE = (PHASE0, ALTAIR)
ALL_FORK_UPGRADES = {
    # pre_fork_name: post_fork_name
    PHASE0: ALTAIR,
    ALTAIR: MERGE,
}
ALL_PRE_POST_FORKS = ALL_FORK_UPGRADES.items()
AFTER_MERGE_UPGRADES = {key: value for key, value in ALL_FORK_UPGRADES.items() if key not in FORKS_BEFORE_ALTAIR}
AFTER_MERGE_PRE_POST_FORKS = AFTER_MERGE_UPGRADES.items()

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
