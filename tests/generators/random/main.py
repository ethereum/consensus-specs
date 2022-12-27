from eth2spec.test.helpers.constants import PHASE0, ALTAIR, BELLATRIX, CAPELLA, EIP4844
from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.random.test_' + key for key in [
        'random',
    ]}
    altair_mods = {key: 'eth2spec.test.altair.random.test_' + key for key in [
        'random',
    ]}
    bellatrix_mods = {key: 'eth2spec.test.bellatrix.random.test_' + key for key in [
        'random',
    ]}
    capella_mods = {key: 'eth2spec.test.capella.random.test_' + key for key in [
        'random',
    ]}
    eip4844_mods = {key: 'eth2spec.test.eip4844.random.test_' + key for key in [
        'random',
    ]}

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        EIP4844: eip4844_mods,
    }

    run_state_test_generators(runner_name="random", all_mods=all_mods)
