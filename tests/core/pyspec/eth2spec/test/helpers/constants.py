from .typing import PresetBaseName, SpecForkName

#
# SpecForkName
#

# Some of the Spec module functionality is exposed here to deal with phase-specific changes.
PHASE0 = SpecForkName("phase0")
ALTAIR = SpecForkName("altair")
BELLATRIX = SpecForkName("bellatrix")
CAPELLA = SpecForkName("capella")
DENEB = SpecForkName("deneb")
ELECTRA = SpecForkName("electra")
FULU = SpecForkName("fulu")
GLOAS = SpecForkName("gloas")

# Experimental phases (not included in default "ALL_PHASES"):
EIP7441 = SpecForkName("eip7441")
EIP7732 = SpecForkName("eip7732")
EIP7782 = SpecForkName("eip7782")
EIP7805 = SpecForkName("eip7805")
EIP7928 = SpecForkName("eip7928")

#
# SpecFork settings
#

# The forks that are deployed on Mainnet
MAINNET_FORKS = (PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA)
LATEST_FORK = MAINNET_FORKS[-1]
# The forks that pytest can run with.
# Note: when adding a new fork here, all tests from previous forks with decorator `with_X_and_later`
#       will run on the new fork. To skip this behaviour, add the fork to `ALLOWED_TEST_RUNNER_FORKS`
ALL_PHASES = (
    # Formal forks
    *MAINNET_FORKS,
    FULU,
    GLOAS,
    # Experimental patches
    EIP7732,
    EIP7782,
    EIP7805,
    EIP7928,
)
# The forks that have light client specs
LIGHT_CLIENT_TESTING_FORKS = [item for item in MAINNET_FORKS if item != PHASE0] + [FULU]
# The forks that output to the test vectors.
TESTGEN_FORKS = (*MAINNET_FORKS, FULU, GLOAS, EIP7732, EIP7782, EIP7805)
# Forks allowed in the test runner `--fork` flag, to fail fast in case of typos
ALLOWED_TEST_RUNNER_FORKS = (*ALL_PHASES, EIP7441)

# NOTE: the same definition as in `pysetup/md_doc_paths.py`
PREVIOUS_FORK_OF = {
    # post_fork_name: pre_fork_name
    PHASE0: None,
    ALTAIR: PHASE0,
    BELLATRIX: ALTAIR,
    CAPELLA: BELLATRIX,
    DENEB: CAPELLA,
    ELECTRA: DENEB,
    FULU: ELECTRA,
    GLOAS: FULU,
    # Experimental patches
    EIP7441: CAPELLA,
    EIP7732: ELECTRA,
    EIP7782: FULU,
    EIP7805: FULU,
    EIP7928: FULU,
}

# For fork transition tests
POST_FORK_OF = {
    # pre_fork_name: post_fork_name
    PHASE0: ALTAIR,
    ALTAIR: BELLATRIX,
    BELLATRIX: CAPELLA,
    CAPELLA: DENEB,
    DENEB: ELECTRA,
    ELECTRA: FULU,
    FULU: GLOAS,
}

ALL_PRE_POST_FORKS = POST_FORK_OF.items()
DENEB_TRANSITION_UPGRADES_AND_AFTER = {
    key: value for key, value in POST_FORK_OF.items() if key not in [PHASE0, ALTAIR, BELLATRIX]
}
ELECTRA_TRANSITION_UPGRADES_AND_AFTER = {
    key: value
    for key, value in POST_FORK_OF.items()
    if key not in [PHASE0, ALTAIR, BELLATRIX, CAPELLA]
}
AFTER_DENEB_PRE_POST_FORKS = DENEB_TRANSITION_UPGRADES_AND_AFTER.items()
AFTER_ELECTRA_PRE_POST_FORKS = ELECTRA_TRANSITION_UPGRADES_AND_AFTER.items()

#
# Config and Preset
#
MAINNET = PresetBaseName("mainnet")
MINIMAL = PresetBaseName("minimal")

ALL_PRESETS = (MINIMAL, MAINNET)


#
# Number
#
UINT64_MAX = 2**64 - 1
