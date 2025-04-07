from eth2spec.gen_helpers.gen_from_tests.gen import (
    run_state_test_generators,
    combine_mods,
    check_mods,
)
from eth2spec.test.helpers.constants import PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU


if __name__ == "__main__":
    phase_0_mods = {
        key: "eth2spec.test.phase0.epoch_processing.test_process_" + key
        for key in [
            "justification_and_finalization",
            "rewards_and_penalties",
            "registry_updates",
            "slashings",
            "eth1_data_reset",
            "effective_balance_updates",
            "slashings_reset",
            "randao_mixes_reset",
            "historical_roots_update",
            "participation_record_updates",
        ]
    }

    _new_altair_mods = {
        key: "eth2spec.test.altair.epoch_processing.test_process_" + key
        for key in [
            "inactivity_updates",
            "participation_flag_updates",
            "sync_committee_updates",
        ]
    }
    altair_mods = combine_mods(_new_altair_mods, phase_0_mods)

    # No epoch-processing changes in Bellatrix and previous testing repeats with new types,
    # so no additional tests required.
    bellatrix_mods = altair_mods

    _new_capella_mods = {
        key: "eth2spec.test.capella.epoch_processing.test_process_" + key
        for key in [
            "historical_summaries_update",
        ]
    }
    capella_mods = combine_mods(_new_capella_mods, bellatrix_mods)

    _new_deneb_mods = {
        key: "eth2spec.test.deneb.epoch_processing.test_process_" + key
        for key in [
            "registry_updates",
        ]
    }
    deneb_mods = combine_mods(_new_deneb_mods, capella_mods)

    _new_electra_mods_1 = {
        key: "eth2spec.test.electra.epoch_processing.test_process_" + key
        for key in [
            "effective_balance_updates",
            "pending_consolidations",
            "registry_updates",
        ]
    }
    # This is a trick to allow tests be split into multiple files and use the same test format.
    _new_electra_mods_2 = {
        key: "eth2spec.test.electra.epoch_processing." + key
        for key in [
            "pending_deposits",
        ]
    }
    _new_electra_mods = {**_new_electra_mods_1, **_new_electra_mods_2}
    electra_mods = combine_mods(_new_electra_mods, deneb_mods)

    # Fulu specific epoch processing tests
    _new_fulu_mods = {key: 'eth2spec.test.fulu.epoch_processing.test_' + key for key in [
        'process_proposer_lookahead',
        'effective_balance_increase_changes_lookahead'
    ]}
    fulu_mods = combine_mods(_new_fulu_mods, electra_mods)

    # TODO Custody Game testgen is disabled for now
    # custody_game_mods = {**{key: 'eth2spec.test.custody_game.epoch_processing.test_process_' + key for key in [
    #     'reveal_deadlines',
    #     'challenge_deadlines',
    #     'custody_final_updates',
    # ]}, **phase_0_mods}  # also run the previous phase 0 tests (but against custody game spec)

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        DENEB: deneb_mods,
        ELECTRA: electra_mods,
        FULU: fulu_mods,
    }
    check_mods(all_mods, "epoch_processing")

    run_state_test_generators(runner_name="epoch_processing", all_mods=all_mods)
