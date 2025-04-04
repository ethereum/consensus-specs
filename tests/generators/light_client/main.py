from eth2spec.test.helpers.constants import ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU
from eth2spec.gen_helpers.gen_from_tests.gen import (
    combine_mods,
    run_state_test_generators,
    check_mods,
)


if __name__ == "__main__":
    altair_mods = {
        key: "eth2spec.test.altair.light_client.test_" + key
        for key in [
            "data_collection",
            "single_merkle_proof",
            "sync",
            "update_ranking",
        ]
    }

    _new_bellatrix_mods = {
        key: "eth2spec.test.bellatrix.light_client.test_" + key
        for key in [
            "data_collection",
            "sync",
        ]
    }
    bellatrix_mods = combine_mods(_new_bellatrix_mods, altair_mods)

    _new_capella_mods = {
        key: "eth2spec.test.capella.light_client.test_" + key
        for key in [
            "data_collection",
            "single_merkle_proof",
            "sync",
        ]
    }
    capella_mods = combine_mods(_new_capella_mods, bellatrix_mods)

    _new_deneb_mods = {
        key: "eth2spec.test.deneb.light_client.test_" + key
        for key in [
            "sync",
        ]
    }
    deneb_mods = combine_mods(_new_deneb_mods, capella_mods)

    # No additional Electra specific light client tests
    electra_mods = deneb_mods

    # No additional Electra specific light client tests
    fulu_mods = electra_mods

    all_mods = {
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
        FULU: fulu_mods,
    }
    check_mods(all_mods, "light_client")

    run_state_test_generators(runner_name="light_client", all_mods=all_mods)
