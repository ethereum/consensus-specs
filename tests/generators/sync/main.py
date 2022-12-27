from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.test.helpers.constants import BELLATRIX, CAPELLA, EIP4844


if __name__ == "__main__":
    bellatrix_mods = {key: 'eth2spec.test.bellatrix.sync.test_' + key for key in [
        'optimistic',
    ]}
    capella_mods = bellatrix_mods
    eip4844_mods = capella_mods

    all_mods = {
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        EIP4844: eip4844_mods,
    }

    run_state_test_generators(runner_name="sync", all_mods=all_mods)
