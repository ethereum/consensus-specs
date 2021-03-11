from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.phase0 import spec as spec_phase0
from eth2spec.altair import spec as spec_altair
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.test.context import PHASE0, PHASE1, ALTAIR


specs = (spec_phase0, spec_altair, spec_phase1)


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.rewards.test_' + key for key in [
        'basic',
        'leak',
        'random',
    ]}
    # No additional altair or phase 1 specific rewards tests, yet.
    altair_mods = phase_0_mods
    phase_1_mods = phase_0_mods

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        PHASE1: phase_1_mods,
    }

    run_state_test_generators(runner_name="rewards", specs=specs, all_mods=all_mods)
