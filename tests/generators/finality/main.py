from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators, check_mods
from eth2spec.test.helpers.constants import PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU


if __name__ == "__main__":
    phase_0_mods = {"finality": "eth2spec.test.phase0.finality.test_finality"}
    altair_mods = phase_0_mods  # No additional Altair specific finality tests
    bellatrix_mods = altair_mods  # No additional Bellatrix specific finality tests
    capella_mods = bellatrix_mods  # No additional Capella specific finality tests
    deneb_mods = capella_mods  # No additional Deneb specific finality tests
    electra_mods = deneb_mods  # No additional Electra specific finality tests
    fulu_mods = electra_mods  # No additional Fulu specific finality tests

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
        FULU: fulu_mods,
    }
    check_mods(all_mods, "finality")

    run_state_test_generators(runner_name="finality", all_mods=all_mods)
