from eth2spec.test.helpers.custody import (
    get_valid_chunk_challenge,
    get_sample_shard_transition,
)
from eth2spec.test.helpers.attestations import (
    get_valid_on_time_attestation,
)
from eth2spec.test.helpers.state import transition_to, transition_to_valid_shard_slot
from eth2spec.test.context import (
    PHASE0,
    MINIMAL,
    spec_state_test,
    with_all_phases_except,
    with_configs,
)
from eth2spec.test.phase0.block_processing.test_process_attestation import run_attestation_processing
from eth2spec.test.phase0.epoch_processing.run_epoch_process_base import run_epoch_processing_with

from eth2spec.test.phase1.block_processing.test_process_chunk_challenge import (
    run_chunk_challenge_processing,
)


def run_process_challenge_deadlines(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_challenge_deadlines')


@with_all_phases_except([PHASE0])
@spec_state_test
@with_configs([MINIMAL], reason="too slow")
def test_validator_slashed_after_chunk_challenge(spec, state):
    transition_to_valid_shard_slot(spec, state)
    transition_to(spec, state, state.slot + 1)  # Make len(offset_slots) == 1
    shard = 0
    offset_slots = spec.get_offset_slots(state, shard)
    shard_transition = get_sample_shard_transition(spec, state.slot, [2**15 // 3] * len(offset_slots))
    attestation = get_valid_on_time_attestation(spec, state, index=shard, signed=True,
                                                shard_transition=shard_transition)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    validator_index = spec.get_beacon_committee(
        state,
        attestation.data.slot,
        attestation.data.index
    )[0]

    challenge = get_valid_chunk_challenge(spec, state, attestation, shard_transition)

    _, _, _ = run_chunk_challenge_processing(spec, state, challenge)

    assert state.validators[validator_index].slashed == 0

    transition_to(spec, state, state.slot + spec.MAX_CHUNK_CHALLENGE_DELAY * spec.SLOTS_PER_EPOCH)

    state.validators[validator_index].slashed = 0

    yield from run_process_challenge_deadlines(spec, state)

    assert state.validators[validator_index].slashed == 1
