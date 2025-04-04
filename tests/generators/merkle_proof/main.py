from eth2spec.test.helpers.constants import DENEB, ELECTRA, FULU
from eth2spec.gen_helpers.gen_from_tests.gen import (
    run_state_test_generators,
    combine_mods,
    check_mods,
)


if __name__ == "__main__":
    deneb_mods = {
        key: "eth2spec.test.deneb.merkle_proof.test_" + key
        for key in [
            "single_merkle_proof",
        ]
    }
    electra_mods = deneb_mods
    _new_fulu_mods = {
        key: "eth2spec.test.fulu.merkle_proof.test_" + key
        for key in [
            "single_merkle_proof",
        ]
    }
    fulu_mods = combine_mods(_new_fulu_mods, electra_mods)

    all_mods = {
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
        FULU: fulu_mods,
    }
    check_mods(all_mods, "merkle_proof")

    run_state_test_generators(runner_name="merkle_proof", all_mods=all_mods)
