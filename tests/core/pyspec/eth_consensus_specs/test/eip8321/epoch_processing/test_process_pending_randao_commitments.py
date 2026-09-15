from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8321_and_later,
)
from eth_consensus_specs.test.helpers.eip8321.randao import (
    get_commitment,
)
from eth_consensus_specs.test.helpers.epoch_processing import (
    run_epoch_processing_with,
)


def queue_commitment(spec, state, validator_index, activation_epoch):
    commitment = get_commitment(spec, validator_index)
    state.pending_randao_commitments.append(
        spec.PendingRandaoCommitment(
            validator_index=validator_index,
            commitment=commitment,
            activation_epoch=activation_epoch,
        )
    )
    return commitment


def run_process_pending_randao_commitments(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_pending_randao_commitments")


@with_eip8321_and_later
@spec_state_test
def test_no_pending_commitments(spec, state):
    yield from run_process_pending_randao_commitments(spec, state)

    assert len(state.pending_randao_commitments) == 0
    assert all(commitment == spec.Bytes32() for commitment in state.randao_commitments)


@with_eip8321_and_later
@spec_state_test
def test_activate_at_next_epoch(spec, state):
    next_epoch = spec.Epoch(spec.get_current_epoch(state) + 1)
    commitment = queue_commitment(spec, state, 0, next_epoch)

    yield from run_process_pending_randao_commitments(spec, state)

    assert state.randao_commitments[0] == commitment
    assert len(state.pending_randao_commitments) == 0


@with_eip8321_and_later
@spec_state_test
def test_not_yet_activated(spec, state):
    next_epoch = spec.Epoch(spec.get_current_epoch(state) + 1)
    queue_commitment(spec, state, 0, spec.Epoch(next_epoch + 1))

    yield from run_process_pending_randao_commitments(spec, state)

    assert state.randao_commitments[0] == spec.Bytes32()
    assert len(state.pending_randao_commitments) == 1


@with_eip8321_and_later
@spec_state_test
def test_activate_overdue(spec, state):
    # An entry whose activation epoch has already passed is applied immediately
    commitment = queue_commitment(spec, state, 0, spec.GENESIS_EPOCH)

    yield from run_process_pending_randao_commitments(spec, state)

    assert state.randao_commitments[0] == commitment
    assert len(state.pending_randao_commitments) == 0


@with_eip8321_and_later
@spec_state_test
def test_drain_prefix_only(spec, state):
    next_epoch = spec.Epoch(spec.get_current_epoch(state) + 1)
    due = [queue_commitment(spec, state, index, next_epoch) for index in range(3)]
    pending = queue_commitment(spec, state, 3, spec.Epoch(next_epoch + 2))

    yield from run_process_pending_randao_commitments(spec, state)

    for index, commitment in enumerate(due):
        assert state.randao_commitments[index] == commitment
    assert state.randao_commitments[3] == spec.Bytes32()
    assert len(state.pending_randao_commitments) == 1
    assert state.pending_randao_commitments[0].commitment == pending
