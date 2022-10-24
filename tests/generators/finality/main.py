from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.test.helpers.constants import PHASE0, ALTAIR, BELLATRIX, CAPELLA


if __name__ == "__main__":
    phase_0_mods = {'finality': 'eth2spec.test.phase0.finality.test_finality'}
    altair_mods = phase_0_mods  # No additional Altair specific finality tests
    bellatrix_mods = altair_mods  # No additional Bellatrix specific finality tests
    capella_mods = bellatrix_mods  # No additional Capella specific finality tests

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
    }

    run_state_test_generators(runner_name="finality", all_mods=all_mods)
