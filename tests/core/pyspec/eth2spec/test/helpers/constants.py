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
EIP7002 = SpecForkName('eip7002')

#
# SpecFork settings
#

# The forks that are deployed on Mainnet
MAINNET_FORKS = (PHASE0, ALTAIR, BELLATRIX, CAPELLA)
LATEST_FORK = MAINNET_FORKS[-1]
# The forks that pytest can run with.
ALL_PHASES = (
    # Formal forks
    *MAINNET_FORKS,
    DENEB,
    # Experimental patches
    EIP6110,
    EIP7002,
)
# The forks that have light client specs
LIGHT_CLIENT_TESTING_FORKS = (*[item for item in MAINNET_FORKS if item != PHASE0], DENEB)
# The forks that output to the test vectors.
TESTGEN_FORKS = (*MAINNET_FORKS, DENEB, EIP6110)

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
# Config and Preset
#
MAINNET = PresetBaseName('mainnet')
MINIMAL = PresetBaseName('minimal')

ALL_PRESETS = (MINIMAL, MAINNET)


#
# Number
#
MAX_UINT_64 = 2**64 - 1
