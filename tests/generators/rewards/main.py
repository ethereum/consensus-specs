from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.phase0 import spec as spec_phase0
from eth2spec.lightclient_patch import spec as spec_lightclient_patch
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.test.context import PHASE0, PHASE1, LIGHTCLIENT_PATCH


specs = (spec_phase0, spec_lightclient_patch, spec_phase1)


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.rewards.test_' + key for key in [
        'basic',
        'leak',
        'random',
    ]}
    # No additional lightclient_patch or phase 1 specific rewards tests, yet.
    lightclient_patch_mods = phase_0_mods
    phase_1_mods = phase_0_mods

    all_mods = {
        PHASE0: phase_0_mods,
        LIGHTCLIENT_PATCH: lightclient_patch_mods,
        PHASE1: phase_1_mods,
    }

    run_state_test_generators(runner_name="rewards", specs=specs, all_mods=all_mods)
