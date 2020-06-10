from eth2spec.test.helpers.custody import (
    get_valid_chunk_challenge,
    get_shard_transition,
    get_valid_custody_key_reveal,
)
from eth2spec.test.helpers.attestations import (
    get_valid_on_time_attestation,
)
from eth2spec.test.helpers.state import next_epoch_via_block, transition_to
from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
)
from eth2spec.test.phase_0.block_processing.test_process_attestation import run_attestation_processing
from eth2spec.test.phase_0.epoch_processing.run_epoch_process_base import run_epoch_processing_with

from eth2spec.test.phase_1.block_processing.test_process_chunk_challenge import (
    run_chunk_challenge_processing,
)
from eth2spec.test.phase_1.block_processing.test_process_custody_key_reveal import run_custody_key_reveal_processing


def run_process_challenge_deadlines(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_challenge_deadlines')


@with_all_phases_except(['phase0'])
@spec_state_test
def test_validator_slashed_after_chunk_challenge(spec, state):
    transition_to(spec, state, state.slot + 1)
    shard = 0
    offset_slots = spec.get_offset_slots(state, shard)
    shard_transition = get_shard_transition(spec, state.slot, [2**15 // 3] * len(offset_slots))
    attestation = get_valid_on_time_attestation(spec, state, index=shard, signed=True,
                                                shard_transition=shard_transition)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    validator_index = spec.get_beacon_committee(
        state,
        attestation.data.slot,
        attestation.data.index
    )[0]

    spec.initiate_validator_exit(state, validator_index)
    assert state.validators[validator_index].withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH)

    assert state.validators[validator_index].withdrawable_epoch == spec.FAR_FUTURE_EPOCH

    while spec.get_current_epoch(state) < state.validators[validator_index].exit_epoch:
        next_epoch_via_block(spec, state)
    while (state.validators[validator_index].next_custody_secret_to_reveal
           <= spec.get_custody_period_for_validator(
               validator_index,
               state.validators[validator_index].exit_epoch - 1)):
        custody_key_reveal = get_valid_custody_key_reveal(spec, state, validator_index=validator_index)
        _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    next_epoch_via_block(spec, state)

    challenge = get_valid_chunk_challenge(spec, state, attestation, shard_transition)

    _, _, _ = run_chunk_challenge_processing(spec, state, challenge)

    assert state.validators[validator_index].slashed == 0

    transition_to(spec, state, state.slot + (spec.CUSTODY_RESPONSE_DEADLINE +
                                             spec.EPOCHS_PER_CUSTODY_PERIOD) * spec.SLOTS_PER_EPOCH)

    yield from run_process_challenge_deadlines(spec, state)

    assert state.validators[validator_index].slashed == 1
