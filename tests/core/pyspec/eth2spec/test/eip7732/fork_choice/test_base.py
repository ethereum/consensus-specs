from eth2spec.test.context import (
    spec_state_test,
    with_eip7732_and_later,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)
from eth2spec.test.helpers.fork_choice import (
    check_head_against_root,
    get_anchor_root,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    output_head_check,
    tick_and_add_block,
)
from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.state import (
    payload_state_transition,
    state_transition_and_sign_block,
)


def run_on_execution_payload(spec, store, signed_envelope, test_steps, valid=True):
    """
    Helper to run spec.on_execution_payload() and append test step.
    Similar to run_on_block() in fork_choice helpers.
    """

    def _append_step(valid=True):
        envelope_name = (
            f"execution_payload_envelope_{signed_envelope.message.beacon_block_root.hex()[:8]}"
        )
        test_steps.append(
            {
                "execution_payload": envelope_name,
                "valid": valid,
            }
        )

    if not valid:
        try:
            spec.on_execution_payload(store, signed_envelope)
        except AssertionError:
            _append_step(valid=False)
            return
        else:
            assert False

    spec.on_execution_payload(store, signed_envelope)
    # Verify the envelope was processed
    envelope_root = signed_envelope.message.beacon_block_root
    assert envelope_root in store.execution_payload_states, "Envelope should be processed in store"
    _append_step()


def create_and_yield_execution_payload_envelope(spec, state, block_root, signed_block):
    """
    Helper to create and yield an execution payload envelope for testing.

    Creates a SignedExecutionPayloadEnvelope with proper EIP7732 fields and yields it
    for SSZ serialization in fork choice tests. The builder_index is extracted from
    the block's execution payload header to ensure consistency.

    Args:
        spec: The EIP7732 specification module
        state: Current beacon state
        block_root: Root of the block this envelope is for
        signed_block: The signed beacon block (must contain signed_execution_payload_header)

    Returns:
        envelope_name: Name of the generated envelope for referencing in test steps

    Usage:
        # In a fork choice test function:
        envelope, envelope_name = yield from create_and_yield_execution_payload_envelope(spec, state, block_root, signed_block)
        run_on_execution_payload(spec, store, envelope, test_steps, valid=True)
    """
    # Get builder_index from the block's execution payload header
    builder_index = signed_block.message.body.signed_execution_payload_header.message.builder_index

    # Create a proper execution payload with correct parent_hash for EIP7732
    payload = build_empty_execution_payload(spec, state)
    # Update parent_hash to match state.latest_block_hash as required by EIP7732
    payload.parent_hash = state.latest_block_hash

    # Simulate the state changes that will occur during execution payload processing
    # to compute the correct state_root for the envelope
    temp_state = state.copy()

    # Cache latest block header state root (from process_execution_payload)
    previous_state_root = temp_state.hash_tree_root()
    if temp_state.latest_block_header.state_root == spec.Root():
        temp_state.latest_block_header.state_root = previous_state_root

    # Apply the key state changes that affect the state root:
    # 1. Process execution requests (empty in our test case, but still affects state)
    #    Note: We don't need to actually process them since we use empty ExecutionRequests()

    # 2. Queue the builder payment (this modifies builder_pending_withdrawals and builder_pending_payments)
    payment = temp_state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + temp_state.slot % spec.SLOTS_PER_EPOCH
    ]
    exit_queue_epoch = spec.compute_exit_epoch_and_update_churn(
        temp_state, payment.withdrawal.amount
    )
    payment.withdrawal.withdrawable_epoch = spec.Epoch(
        exit_queue_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    temp_state.builder_pending_withdrawals.append(payment.withdrawal)
    temp_state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + temp_state.slot % spec.SLOTS_PER_EPOCH
    ] = spec.BuilderPendingPayment()

    # 3. Update execution payload availability
    temp_state.execution_payload_availability[temp_state.slot % spec.SLOTS_PER_HISTORICAL_ROOT] = (
        0b1
    )
    # 4. Update latest block hash
    temp_state.latest_block_hash = payload.block_hash
    # 5. Update latest full slot
    temp_state.latest_full_slot = temp_state.slot

    # Compute the post-processing state root
    post_processing_state_root = temp_state.hash_tree_root()

    # Create the execution payload envelope message
    envelope_message = spec.ExecutionPayloadEnvelope(
        beacon_block_root=block_root,
        payload=payload,
        execution_requests=spec.ExecutionRequests(),
        builder_index=builder_index,
        slot=signed_block.message.slot,
        blob_kzg_commitments=[],
        state_root=post_processing_state_root,
    )

    # Sign the envelope with the builder's private key
    builder_privkey = privkeys[envelope_message.builder_index]
    signature = spec.get_execution_payload_envelope_signature(
        state, envelope_message, builder_privkey
    )

    # Create the signed envelope
    envelope = spec.SignedExecutionPayloadEnvelope(
        message=envelope_message,
        signature=signature,
    )
    envelope_name = f"execution_payload_envelope_{block_root.hex()[:8]}"
    yield envelope_name, envelope
    return envelope, envelope_name


@with_eip7732_and_later
@spec_state_test
def test_genesis(spec, state):
    """Test genesis initialization with EIP7732 fork choice modifications"""
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)

    # EIP7732-specific assertions
    assert hasattr(store, "execution_payload_states"), (
        "Store should have execution_payload_states field"
    )
    assert hasattr(store, "ptc_vote"), "Store should have ptc_vote field"
    assert anchor_root in store.execution_payload_states, (
        "Anchor block should be in execution_payload_states"
    )
    assert anchor_root in store.ptc_vote, "Anchor block should have ptc_vote entry"

    # Check PTC vote initialization
    ptc_vote = store.ptc_vote[anchor_root]
    assert len(ptc_vote) == spec.PTC_SIZE, f"PTC vote should have {spec.PTC_SIZE} entries"
    assert all(vote == False for vote in ptc_vote), "All PTC votes should be False initially"

    # Verify get_head returns ForkChoiceNode
    head = spec.get_head(store)
    assert isinstance(head, spec.ForkChoiceNode), "get_head should return ForkChoiceNode in EIP7732"

    output_head_check(spec, store, test_steps)

    yield "steps", test_steps


@with_eip7732_and_later
@spec_state_test
def test_basic(spec, state):
    """Basic EIP7732 fork choice test with execution payload processing"""
    test_steps = []

    # Add EIP7732-specific metadata
    yield "test_scenario", "meta", "basic_fork_choice_eip7732"
    yield "tests_payload_status", "meta", True
    yield "tests_execution_payload_states", "meta", True

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    # Set initial time and record tick
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    # Verify initial EIP7732 state
    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)

    # Check initial head - genesis has FULL payload status
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_FULL, "Genesis head should have FULL status"

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Verify block was added to stores
    block_root = signed_block.message.hash_tree_root()
    assert block_root in store.blocks, "Block should be in store.blocks"
    assert block_root in store.block_states, "Block should have block state"
    assert block_root in store.ptc_vote, "Block should have PTC vote entry"

    # Head should now be the new block with EMPTY status (no payload revealed yet)
    check_head_against_root(spec, store, block_root)
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY, (
        "New head should have EMPTY status (no payload revealed)"
    )

    # Create and yield execution payload envelope first (builder reveals payload)
    envelope, envelope_name = yield from create_and_yield_execution_payload_envelope(
        spec, state, block_root, signed_block
    )

    # Process the execution payload through fork choice on_execution_payload
    run_on_execution_payload(spec, store, envelope, test_steps, valid=True)

    # Then simulate execution payload processing (process the revealed payload)
    payload_state_transition(spec, store, signed_block.message)

    # Verify block now has execution payload state after processing
    assert block_root in store.execution_payload_states, (
        "Block should now have execution payload state"
    )

    # On receiving a block of next slot
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)
    yield from tick_and_add_block(spec, store, signed_block_2, test_steps)

    # Process second block
    block_2_root = signed_block_2.message.hash_tree_root()
    check_head_against_root(spec, store, block_2_root)

    # Create and yield second execution payload envelope first (builder reveals payload)
    envelope_2, envelope_2_name = yield from create_and_yield_execution_payload_envelope(
        spec, state, block_2_root, signed_block_2
    )

    # Process the second execution payload through fork choice on_execution_payload
    run_on_execution_payload(spec, store, envelope_2, test_steps, valid=True)

    # Then simulate execution payload processing for second block
    payload_state_transition(spec, store, signed_block_2.message)

    # Add EIP7732-specific checks to test steps
    test_steps.append(
        {
            "checks": {
                "execution_payload_states_count": len(store.execution_payload_states),
                "blocks_with_ptc_votes": len(store.ptc_vote),
                "head_payload_status": int(spec.get_head(store).payload_status),
            }
        }
    )

    yield "steps", test_steps
