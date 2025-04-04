from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators, check_mods
from eth2spec.test.helpers.constants import BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU


if __name__ == "__main__":
    bellatrix_mods = {
        key: "eth2spec.test.bellatrix.sync.test_" + key
        for key in [
            "optimistic",
        ]
    }
    capella_mods = bellatrix_mods
    deneb_mods = capella_mods
    electra_mods = deneb_mods
    fulu_mods = electra_mods

    all_mods = {
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
        FULU: fulu_mods,
    }
    check_mods(all_mods, "sync")

    run_state_test_generators(runner_name="sync", all_mods=all_mods)
