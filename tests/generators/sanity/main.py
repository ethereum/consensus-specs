from eth2spec.test.helpers.constants import PHASE0, ALTAIR, BELLATRIX, CAPELLA
from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators, combine_mods


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.sanity.test_' + key for key in [
        'blocks',
        'slots',
    ]}

    _new_altair_mods = {key: 'eth2spec.test.altair.sanity.test_' + key for key in [
        'blocks',
    ]}
    altair_mods = combine_mods(_new_altair_mods, phase_0_mods)

    _new_bellatrix_mods = {key: 'eth2spec.test.bellatrix.sanity.test_' + key for key in [
        'blocks',
    ]}
    bellatrix_mods = combine_mods(_new_bellatrix_mods, altair_mods)

    _new_capella_mods = {key: 'eth2spec.test.capella.sanity.test_' + key for key in [
        'blocks',
    ]}
    capella_mods = combine_mods(_new_capella_mods, bellatrix_mods)

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
    }

    run_state_test_generators(runner_name="sanity", all_mods=all_mods)
