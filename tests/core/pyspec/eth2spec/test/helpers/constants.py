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
# TODO: everything runs in parallel to Altair.
# After features are rebased on the Altair fork, this can be reduced to just PHASE0.
FORKS_BEFORE_ALTAIR = (PHASE0, MERGE, SHARDING, CUSTODY_GAME, DAS)

# TODO: when rebasing Merge onto Altair, add ALTAIR to this tuple.
FORKS_BEFORE_MERGE = (PHASE0,)

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
