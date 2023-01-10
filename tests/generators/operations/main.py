from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators, combine_mods
from eth2spec.test.helpers.constants import PHASE0, ALTAIR, BELLATRIX, CAPELLA, EIP4844


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.block_processing.test_process_' + key for key in [
        'attestation',
        'attester_slashing',
        'block_header',
        'deposit',
        'proposer_slashing',
        'voluntary_exit',
    ]}
    _new_altair_mods = {
        **{'sync_aggregate': [
            'eth2spec.test.altair.block_processing.sync_aggregate.test_process_' + key
            for key in ['sync_aggregate', 'sync_aggregate_random']
        ]},
        **{key: 'eth2spec.test.altair.block_processing.test_process_' + key for key in [
            'deposit',
        ]}
    }
    altair_mods = combine_mods(_new_altair_mods, phase_0_mods)

    _new_bellatrix_mods = {key: 'eth2spec.test.bellatrix.block_processing.test_process_' + key for key in [
        'deposit',
        'execution_payload',
        'voluntary_exit',
    ]}
    bellatrix_mods = combine_mods(_new_bellatrix_mods, altair_mods)

    _new_capella_mods = {key: 'eth2spec.test.capella.block_processing.test_process_' + key for key in [
        'deposit',
        'bls_to_execution_change',
        'withdrawals',
    ]}
    capella_mods = combine_mods(_new_capella_mods, bellatrix_mods)

    eip4844_mods = capella_mods

    # TODO Custody Game testgen is disabled for now
    # _new_custody_game_mods = {key: 'eth2spec.test.custody_game.block_processing.test_process_' + key for key in [
    #     'attestation',
    #     'chunk_challenge',
    #     'custody_key_reveal',
    #     'custody_slashing',
    #     'early_derived_secret_reveal',
    # ]}
    # custody_game_mods = combine_mods(_new_custody_game_mods, phase0_mods)

    all_mods = {
        PHASE0: phase_0_mods,
        ALTAIR: altair_mods,
        BELLATRIX: bellatrix_mods,
        CAPELLA: capella_mods,
        EIP4844: eip4844_mods,
    }

    run_state_test_generators(runner_name="operations", all_mods=all_mods)
