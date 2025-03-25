from eth2spec.gen_helpers.gen_from_tests.gen import (
    run_state_test_generators,
    combine_mods,
    check_mods,
)
from eth2spec.test.helpers.constants import (
    PHASE0,
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    ELECTRA,
    FULU,
)


if __name__ == "__main__":
    phase_0_mods = {
        key: "eth2spec.test.phase0.block_processing.test_process_" + key
        for key in [
            "attestation",
            "attester_slashing",
            "block_header",
            "deposit",
            "proposer_slashing",
            "voluntary_exit",
        ]
    }
    _new_altair_mods = {
        **{
            "sync_aggregate": [
                "eth2spec.test.altair.block_processing.sync_aggregate.test_process_"
                + key
                for key in ["sync_aggregate", "sync_aggregate_random"]
            ]
        },
        **{
            key: "eth2spec.test.altair.block_processing.test_process_" + key
            for key in [
                "deposit",
            ]
        },
    }
    altair_mods = combine_mods(_new_altair_mods, phase_0_mods)

    _new_bellatrix_mods = {
        key: "eth2spec.test.bellatrix.block_processing.test_process_" + key
        for key in [
            "deposit",
            "execution_payload",
            "voluntary_exit",
        ]
    }
    bellatrix_mods = combine_mods(_new_bellatrix_mods, altair_mods)

    _new_capella_mods = {
        key: "eth2spec.test.capella.block_processing.test_process_" + key
        for key in [
            "bls_to_execution_change",
            "deposit",
            "execution_payload",
            "withdrawals",
        ]
    }
    capella_mods = combine_mods(_new_capella_mods, bellatrix_mods)

    _new_deneb_mods = {
        key: "eth2spec.test.deneb.block_processing.test_process_" + key
        for key in [
            "execution_payload",
            "voluntary_exit",
        ]
    }
    deneb_mods = combine_mods(_new_deneb_mods, capella_mods)

    _new_electra_mods = {
        key: "eth2spec.test.electra.block_processing.test_process_" + key
        for key in [
            "attestation",
            "consolidation_request",
            "deposit_request",
            "voluntary_exit",
            "withdrawal_request",
            "withdrawals",
        ]
    }
    electra_mods = combine_mods(_new_electra_mods, deneb_mods)

    # No additional Fulu specific block processing tests
    fulu_mods = electra_mods

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
        FULU: fulu_mods,
    }
    check_mods(all_mods, "block_processing")

    run_state_test_generators(runner_name="operations", all_mods=all_mods)
