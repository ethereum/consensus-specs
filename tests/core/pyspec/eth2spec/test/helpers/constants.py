from .typing import SpecForkName, PresetBaseName


#
# SpecForkName
#
# Some of the Spec module functionality is exposed here to deal with phase-specific changes.
PHASE0 = SpecForkName('phase0')
ALTAIR = SpecForkName('altair')
BELLATRIX = SpecForkName('bellatrix')
CAPELLA = SpecForkName('capella')
DENEB = SpecForkName('deneb')

# Experimental phases (not included in default "ALL_PHASES"):
SHARDING = SpecForkName('sharding')
CUSTODY_GAME = SpecForkName('custody_game')
DAS = SpecForkName('das')
EIP6110 = SpecForkName('eip6110')
ATTSLOTRANGE = SpecForkName('attslotrange')

# The forks that pytest can run with.
ALL_PHASES = (
    # Formal forks
    PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB,
    # Experimental patches
    EIP6110, ATTSLOTRANGE,
)
# The forks that output to the test vectors.
TESTGEN_FORKS = (PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB, EIP6110)

ALL_FORK_UPGRADES = {
    # pre_fork_name: post_fork_name
    PHASE0: ALTAIR,
    ALTAIR: BELLATRIX,
    BELLATRIX: CAPELLA,
    CAPELLA: DENEB,
    DENEB: EIP6110,
}
ALL_PRE_POST_FORKS = ALL_FORK_UPGRADES.items()
AFTER_BELLATRIX_UPGRADES = {key: value for key, value in ALL_FORK_UPGRADES.items() if key != PHASE0}
AFTER_BELLATRIX_PRE_POST_FORKS = AFTER_BELLATRIX_UPGRADES.items()
AFTER_CAPELLA_UPGRADES = {key: value for key, value in ALL_FORK_UPGRADES.items()
                          if key not in [PHASE0, ALTAIR]}
AFTER_CAPELLA_PRE_POST_FORKS = AFTER_CAPELLA_UPGRADES.items()
AFTER_DENEB_UPGRADES = {key: value for key, value in ALL_FORK_UPGRADES.items()
                        if key not in [PHASE0, ALTAIR, BELLATRIX]}
AFTER_DENEB_PRE_POST_FORKS = AFTER_DENEB_UPGRADES.items()

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
