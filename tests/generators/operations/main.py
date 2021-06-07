from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.test.helpers.constants import PHASE0, ALTAIR, MERGE


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.block_processing.test_process_' + key for key in [
        'attestation',
        'attester_slashing',
        'block_header',
        'deposit',
        'proposer_slashing',
        'voluntary_exit',
    ]}
    altair_mods = {
        **{key: 'eth2spec.test.altair.block_processing.test_process_' + key for key in [
            'sync_aggregate',
        ]},
        **phase_0_mods,
    }  # also run the previous phase 0 tests

    merge_mods = {
        **{key: 'eth2spec.test.merge.block_processing.test_process_' + key for key in [
            'execution_payload',
        ]},
        **phase_0_mods,  # TODO: runs phase0 tests. Rebase to include `altair_mods` testing later.
    }

    # TODO Custody Game testgen is disabled for now
    # custody_game_mods = {**{key: 'eth2spec.test.custody_game.block_processing.test_process_' + key for key in [
    #     'attestation',
    #     'chunk_challenge',
    #     'custody_key_reveal',
    #     'custody_slashing',
    #     'early_derived_secret_reveal',
    # ]}, **phase_0_mods}  # also run the previous phase 0 tests (but against custody game spec)

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        MERGE: merge_mods,
    }

    run_state_test_generators(runner_name="operations", all_mods=all_mods)
