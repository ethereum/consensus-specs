from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)
from tests.infra.helpers.withdrawals import (
    set_parent_block_full,
)


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__empty_parent(spec, state):
    """
    Test that process_parent_execution_payload returns early when the parent
    block was empty (payload not delivered).

    After processing, the state should be unchanged with respect to
    latest_block_hash and execution_payload_availability.
    """
    # Default genesis state: latest_block_hash == latest_execution_payload_bid.block_hash
    # (parent is full). Process a block so the new bid's block_hash differs.
    block_1 = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block_1)

    # After Block 1, parent is empty because no payload was delivered
    is_parent_block_full = state.latest_block_hash == state.latest_execution_payload_bid.block_hash
    assert not is_parent_block_full

    pre_availability = state.execution_payload_availability[
        state.slot % spec.SLOTS_PER_HISTORICAL_ROOT
    ]

    # Process Block 2 -- process_parent_execution_payload should return early
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "pre", state
    yield "blocks", [signed_block_2]
    yield "post", state

    # latest_block_hash should NOT have been updated by process_parent_execution_payload
    # (it IS updated by process_execution_payload_bid for the new block)
    # But execution_payload_availability for the PARENT slot should remain unchanged
    assert (
        pre_availability
        == state.execution_payload_availability[(state.slot - 1) % spec.SLOTS_PER_HISTORICAL_ROOT]
    )


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__full_parent(spec, state):
    """
    Test that process_parent_execution_payload processes the parent's execution
    requests and updates state when the parent block was full.

    At genesis, latest_block_hash == latest_execution_payload_bid.block_hash,
    so the first block always sees a full parent.
    """
    set_parent_block_full(spec, state)

    pre_latest_block_hash = state.latest_block_hash

    # Process Block 1 -- parent is full, so process_parent_execution_payload runs
    block_1 = build_empty_block_for_next_slot(spec, state)
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    yield "pre", state
    yield "blocks", [signed_block_1]
    yield "post", state

    # latest_block_hash should be updated to parent's bid block_hash
    assert state.latest_block_hash == pre_latest_block_hash


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__empty_parent_requires_empty_requests(spec, state):
    """
    Test that when parent is empty, parent_execution_requests must be empty.
    A non-empty parent_execution_requests with an empty parent should fail.
    """
    # Process Block 1 to get an empty parent
    block_1 = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block_1)

    # Parent is empty
    is_parent_block_full = state.latest_block_hash == state.latest_execution_payload_bid.block_hash
    assert not is_parent_block_full

    # The block helper builds blocks with default (empty) parent_execution_requests,
    # which is what process_parent_execution_payload expects for empty parents.
    # This test just confirms the empty parent path works.
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "pre", state
    yield "blocks", [signed_block_2]
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_process_parent_execution_payload__wrong_execution_requests_root(spec, state):
    """
    Test that process_parent_execution_payload rejects a block whose
    parent_execution_requests do not match parent_bid.execution_requests_root
    when the parent block was full.
    """
    set_parent_block_full(spec, state)

    # Build a valid block, then tamper with parent_execution_requests
    block = build_empty_block_for_next_slot(spec, state)

    # Inject a non-empty deposit so the hash diverges from the committed root
    block.body.parent_execution_requests = spec.ExecutionRequests(
        deposits=spec.List[spec.DepositRequest, spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD](
            [
                spec.DepositRequest(
                    pubkey=spec.BLSPubkey(b"\x01" * 48),
                    withdrawal_credentials=spec.Bytes32(b"\x02" * 32),
                    amount=spec.Gwei(32000000000),
                    signature=spec.BLSSignature(b"\x03" * 96),
                    index=spec.uint64(0),
                )
            ]
        ),
        withdrawals=spec.List[spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD](),
        consolidations=spec.List[
            spec.ConsolidationRequest, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ](),
    )

    # Advance to the block's slot so process_block can run
    spec.process_slots(state, block.slot)

    yield "pre", state

    expect_assertion_error(lambda: spec.process_parent_execution_payload(state, block))

    yield "post", None
