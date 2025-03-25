from eth2spec.test.helpers.constants import (
    PHASE0,
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    ELECTRA,
    FULU,
)
from eth2spec.gen_helpers.gen_from_tests.gen import (
    run_state_test_generators,
    check_mods,
)


if __name__ == "__main__":
    phase_0_mods = {
        key: "eth2spec.test.phase0.random.test_" + key
        for key in [
            "random",
        ]
    }
    altair_mods = {
        key: "eth2spec.test.altair.random.test_" + key
        for key in [
            "random",
        ]
    }
    bellatrix_mods = {
        key: "eth2spec.test.bellatrix.random.test_" + key
        for key in [
            "random",
        ]
    }
    capella_mods = {
        key: "eth2spec.test.capella.random.test_" + key
        for key in [
            "random",
        ]
    }
    deneb_mods = {
        key: "eth2spec.test.deneb.random.test_" + key
        for key in [
            "random",
        ]
    }
    electra_mods = {
        key: "eth2spec.test.electra.random.test_" + key
        for key in [
            "random",
        ]
    }
    fulu_mods = {
        key: "eth2spec.test.fulu.random.test_" + key
        for key in [
            "random",
        ]
    }

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
        FULU: fulu_mods,
    }
    check_mods(all_mods, "random")

    run_state_test_generators(runner_name="random", all_mods=all_mods)
