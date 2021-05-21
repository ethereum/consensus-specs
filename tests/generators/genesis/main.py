from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.test.helpers.constants import PHASE0, ALTAIR


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.genesis.test_' + key for key in [
        'initialization',
        'validity',
    ]}
    altair_mods = phase_0_mods
    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
    }

    run_state_test_generators(runner_name="genesis", all_mods=all_mods)
