from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_requests import (
    get_non_empty_execution_requests,
)
from tests.infra.helpers.withdrawals import set_parent_block_full


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


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__empty_parent(spec, state):
    """
    Test that process_parent_execution_payload returns early when the parent
    block was empty (payload not delivered).
    """
    block = build_empty_block_for_next_slot(spec, state)

    is_parent_block_full = (
        block.body.signed_execution_payload_bid.message.parent_block_hash
        == state.latest_execution_payload_bid.block_hash
    )
    assert not is_parent_block_full

    pre_latest_block_hash = state.latest_block_hash
    parent_slot = state.latest_execution_payload_bid.slot
    pre_availability = state.execution_payload_availability[
        parent_slot % spec.SLOTS_PER_HISTORICAL_ROOT
    ]

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert state.latest_block_hash == pre_latest_block_hash
    assert (
        state.execution_payload_availability[parent_slot % spec.SLOTS_PER_HISTORICAL_ROOT]
        == pre_availability
    )


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__full_parent(spec, state):
    """
    Test that process_parent_execution_payload processes the parent's execution
    requests and updates state when the parent block was full.
    """
    set_parent_block_full(spec, state)
    block = build_empty_block_for_next_slot(spec, state)

    parent_bid = state.latest_execution_payload_bid.copy()
    parent_slot_index = parent_bid.slot % spec.SLOTS_PER_HISTORICAL_ROOT
    state.execution_payload_availability[parent_slot_index] = 0b0

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block)

    assert state.latest_block_hash == parent_bid.block_hash
    assert state.execution_payload_availability[parent_slot_index] == 0b1


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__empty_parent_requires_empty_requests(spec, state):
    """
    Test that when parent is empty, parent_execution_requests must be empty.
    """
    block = build_empty_block_for_next_slot(spec, state)

    is_parent_block_full = (
        block.body.signed_execution_payload_bid.message.parent_block_hash
        == state.latest_execution_payload_bid.block_hash
    )
    assert not is_parent_block_full

    block.body.parent_execution_requests = get_non_empty_execution_requests(spec)

    spec.process_slots(state, block.slot)
    yield from run_parent_execution_payload_processing(spec, state, block, valid=False)
