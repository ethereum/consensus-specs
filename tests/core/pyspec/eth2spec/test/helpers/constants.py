from .typing import SpecForkName, ConfigName


#
# SpecForkName
#
# Some of the Spec module functionality is exposed here to deal with phase-specific changes.
PHASE0 = SpecForkName('phase0')
ALTAIR = SpecForkName('altair')

# Experimental phases (not included in default "ALL_PHASES"):
MERGE = SpecForkName('merge')
SHARDING = SpecForkName('sharding')
CUSTODY_GAME = SpecForkName('custody_game')
DAS = SpecForkName('das')

# The forks that pytest runs with.
ALL_PHASES = (PHASE0, ALTAIR)
# The forks that output to the test vectors.
TESTGEN_FORKS = (PHASE0, ALTAIR)
# TODO: everything runs in parallel to Altair.
# After features are rebased on the Altair fork, this can be reduced to just PHASE0.
FORKS_BEFORE_ALTAIR = (PHASE0, MERGE, SHARDING, CUSTODY_GAME, DAS)

#
# Config
#
MAINNET = ConfigName('mainnet')
MINIMAL = ConfigName('minimal')

ALL_CONFIGS = (MINIMAL, MAINNET)
