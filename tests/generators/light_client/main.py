from eth2spec.test.helpers.constants import ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA
from eth2spec.gen_helpers.gen_from_tests.gen import combine_mods, run_state_test_generators


if __name__ == "__main__":
    altair_mods = {key: 'eth2spec.test.altair.light_client.test_' + key for key in [
        'single_merkle_proof',
        'sync',
        'update_ranking',
    ]}
    bellatrix_mods = altair_mods

    _new_capella_mods = {key: 'eth2spec.test.capella.light_client.test_' + key for key in [
        'single_merkle_proof',
    ]}
    capella_mods = combine_mods(_new_capella_mods, bellatrix_mods)
    deneb_mods = capella_mods
    electra_mods = deneb_mods

    all_mods = {
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
    }

    run_state_test_generators(runner_name="light_client", all_mods=all_mods)
