from eth2spec.test.helpers.constants import PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB
from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators, combine_mods


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.api.test_' + key for key in [
        # 'api', TODO
    ]}

    _new_altair_mods = {key: 'eth2spec.test.altair.api.test_' + key for key in [
        # 'api', TODO
    ]}
    altair_mods = combine_mods(_new_altair_mods, phase_0_mods)

    _new_bellatrix_mods = {key: 'eth2spec.test.bellatrix.api.test_' + key for key in [
        # 'api', TODO
    ]}
    bellatrix_mods = combine_mods(_new_bellatrix_mods, altair_mods)

    _new_capella_mods = {key: 'eth2spec.test.capella.api.test_' + key for key in [
        'api',
    ]}
    capella_mods = combine_mods(_new_capella_mods, bellatrix_mods)

    _new_deneb_mods = {key: 'eth2spec.test.deneb.api.test_' + key for key in [
        # 'api', TODO
    ]}
    deneb_mods = combine_mods(_new_deneb_mods, capella_mods)

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
    }

    run_state_test_generators(runner_name="api", all_mods=all_mods)
