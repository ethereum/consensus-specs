from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_eip8148_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.withdrawals import (
    prepare_set_sweep_threshold_request,
    set_compounding_withdrawal_credential_with_balance,
    set_parent_block_full,
)


def _set_compounding_validator(spec, state, validator_index):
    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE
    )
    state.validator_sweep_thresholds[validator_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA


def _commit_parent_requests(spec, state, requests):
    """
    Configure state so the parent block was FULL and the parent bid commits
    to ``requests``.
    """
    set_parent_block_full(spec, state)
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)


def run_parent_execution_payload_processing(spec, state, block, valid=True):
    """
    Run ``process_parent_execution_payload`` against a prepared pre-state.
    """
    yield "pre", state
    yield "block", block

    if not valid:
        expect_assertion_error(lambda: spec.process_parent_execution_payload(state, block))
        yield "post", None
        return

    spec.process_parent_execution_payload(state, block)
    yield "post", state


@with_eip8148_and_later
@spec_state_test
def test_process_parent_execution_payload__set_sweep_threshold_request_applied(spec, state):
    """
    Test that a set sweep threshold request in the parent's execution requests
    updates the validator's sweep threshold.
    """
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index)
    threshold = spec.MIN_ACTIVATION_BALANCE
    assert state.validator_sweep_thresholds[validator_index] != threshold

    requests = spec.ExecutionRequests(
        sweep_thresholds=spec.SweepThresholdRequests(
            [prepare_set_sweep_threshold_request(spec, state, validator_index, threshold)]
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_process_parent_execution_payload__multiple_sweep_threshold_requests(spec, state):
    """
    Test that every set sweep threshold request of the parent's execution
    requests is applied in order, so that the last request for a given
    validator wins.
    """
    first_index = 7
    second_index = 12
    for validator_index in (first_index, second_index):
        _set_compounding_validator(spec, state, validator_index)
    overridden_threshold = spec.MIN_ACTIVATION_BALANCE
    first_threshold = spec.MIN_ACTIVATION_BALANCE + 12 * spec.EFFECTIVE_BALANCE_INCREMENT
    second_threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT

    requests = spec.ExecutionRequests(
        sweep_thresholds=spec.SweepThresholdRequests(
            [
                prepare_set_sweep_threshold_request(spec, state, first_index, overridden_threshold),
                prepare_set_sweep_threshold_request(spec, state, second_index, second_threshold),
                prepare_set_sweep_threshold_request(spec, state, first_index, first_threshold),
            ]
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert state.validator_sweep_thresholds[first_index] == first_threshold
    assert state.validator_sweep_thresholds[second_index] == second_threshold


@with_eip8148_and_later
@spec_state_test
def test_process_parent_execution_payload__invalid_sweep_threshold_request_no_op(spec, state):
    """
    Test that an invalid set sweep threshold request (unknown pubkey) in the
    parent's execution requests is a no-op while the payload is still applied.
    """
    requests = spec.ExecutionRequests(
        sweep_thresholds=spec.SweepThresholdRequests(
            [
                spec.SetSweepThresholdRequest(
                    source_address=spec.ExecutionAddress(b"\x42" * 20),
                    validator_pubkey=spec.BLSPubkey(b"\x99" * 48),
                    threshold=spec.MIN_ACTIVATION_BALANCE,
                )
            ]
        ),
    )
    _commit_parent_requests(spec, state, requests)
    parent_bid = state.latest_execution_payload_bid.copy()
    parent_slot_index = parent_bid.slot % spec.SLOTS_PER_HISTORICAL_ROOT

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    pre_thresholds = state.validator_sweep_thresholds.copy()

    # Clear the effects of applying the parent payload, so that the
    # post-conditions below fail if the payload is not applied
    state.execution_payload_availability[parent_slot_index] = 0b0
    state.latest_block_hash = spec.Hash32(b"\x24" * 32)

    yield from run_parent_execution_payload_processing(spec, state, block)

    assert state.validator_sweep_thresholds == pre_thresholds
    assert state.execution_payload_availability[parent_slot_index] == 0b1
    assert state.latest_block_hash == parent_bid.block_hash


@with_eip8148_and_later
@spec_state_test
def test_max_set_sweep_threshold_requests(spec, state):
    requests = spec.ExecutionRequests(
        sweep_thresholds=spec.SweepThresholdRequests(
            [spec.SetSweepThresholdRequest()] * spec.MAX_SET_SWEEP_THRESHOLD_REQUESTS_PER_PAYLOAD
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)


@with_eip8148_and_later
@spec_state_test
def test_invalid_too_many_set_sweep_threshold_requests(spec, state):
    requests = spec.ExecutionRequests(
        sweep_thresholds=spec.SweepThresholdRequests(
            [spec.SetSweepThresholdRequest()]
            * (spec.MAX_SET_SWEEP_THRESHOLD_REQUESTS_PER_PAYLOAD + 1)
        ),
    )
    _commit_parent_requests(spec, state, requests)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)
