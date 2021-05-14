from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.phase0 import spec as spec_phase0
from eth2spec.altair import spec as spec_altair
from eth2spec.merge import spec as spec_merge
from eth2spec.test.helpers.constants import PHASE0, ALTAIR, MERGE


specs = (spec_phase0, spec_altair, spec_merge)


if __name__ == "__main__":
    phase_0_mods = {'finality': 'eth2spec.test.phase0.finality.test_finality'}
    altair_mods = phase_0_mods   # No additional Altair specific finality tests
    merge_mods = phase_0_mods    # No additional Merge specific finality tests

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        MERGE: spec_merge,
    }

    run_state_test_generators(runner_name="finality", specs=specs, all_mods=all_mods)
