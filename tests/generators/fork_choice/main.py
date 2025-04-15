from eth2spec.gen_helpers.gen_from_tests.gen import (
    run_state_test_generators,
    combine_mods,
    check_mods,
)
from eth2spec.test.helpers.constants import ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU


if __name__ == "__main__":
    # Note: Fork choice tests start from Altair - there are no fork choice test for phase 0 anymore
    altair_mods = {
        key: "eth2spec.test.phase0.fork_choice.test_" + key
        for key in [
            "get_head",
            "on_block",
            "ex_ante",
            "reorg",
            "withholding",
            "get_proposer_head",
        ]
    }

    # For merge `on_merge_block` test kind added with `pow_block_N.ssz` files with several
    # PowBlock's which should be resolved by `get_pow_block(hash: Hash32) -> PowBlock` function
    _new_bellatrix_mods = {
        key: "eth2spec.test.bellatrix.fork_choice.test_" + key
        for key in [
            "on_merge_block",
            "should_override_forkchoice_update",
        ]
    }
    bellatrix_mods = combine_mods(_new_bellatrix_mods, altair_mods)
    capella_mods = bellatrix_mods  # No additional Capella specific fork choice tests

    # Deneb adds `is_data_available` tests
    _new_deneb_mods = {
        key: "eth2spec.test.deneb.fork_choice.test_" + key
        for key in [
            "on_block",
        ]
    }
    deneb_mods = combine_mods(_new_deneb_mods, capella_mods)

    _new_electra_mods = {
        key: "eth2spec.test.electra.fork_choice.test_" + key
        for key in [
            "deposit_with_reorg",
        ]
    }
    electra_mods = combine_mods(_new_electra_mods, deneb_mods)

    # Fulu adds new `is_data_available` tests
    _new_fulu_mods = {
        key: "eth2spec.test.fulu.fork_choice.test_" + key
        for key in [
            "on_block",
        ]
    }
    fulu_mods = combine_mods(_new_fulu_mods, electra_mods)

    all_mods = {
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
        FULU: fulu_mods,
    }
    check_mods(all_mods, "fork_choice")

    run_state_test_generators(runner_name="fork_choice", all_mods=all_mods)
