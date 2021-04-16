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


#
# Config
#
MAINNET = ConfigName('mainnet')
MINIMAL = ConfigName('minimal')

ALL_CONFIGS = (MINIMAL, MAINNET)
