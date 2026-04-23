from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.consolidations import (
    prepare_switch_to_compounding_request,
)
from eth_consensus_specs.test.helpers.constants import GLOAS
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    run_on_block,
    run_on_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)

SAMPLE_PAYLOAD_ID = b"\x12" * 8


class CaptureEngine:
    def __init__(self):
        self.head_block_hash = None
        self.payload_attributes = None

    def notify_forkchoice_updated(
        self, head_block_hash, safe_block_hash, finalized_block_hash, payload_attributes
    ):
        self.head_block_hash = head_block_hash
        self.payload_attributes = payload_attributes
        return SAMPLE_PAYLOAD_ID


def _add_block_to_store(spec, state, execution_requests=None):
    """
    Build block_1, process it, and add it to the store. If execution_requests
    is provided, the block's bid commits to their hash so the child envelope
    can deliver them.
    """
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    spec.on_tick(store, current_time)

    block = build_empty_block_for_next_slot(spec, state)

    if execution_requests is not None:
        bid = block.body.signed_execution_payload_bid.message
        bid.execution_requests_root = spec.hash_tree_root(execution_requests)
        if bid.builder_index == spec.BUILDER_INDEX_SELF_BUILD:
            block.body.signed_execution_payload_bid = spec.SignedExecutionPayloadBid(
                message=bid,
                signature=spec.G2_POINT_AT_INFINITY,
            )

    signed_block = state_transition_and_sign_block(spec, state, block)
    block_time = (
        store.genesis_time + signed_block.message.slot * spec.config.SLOT_DURATION_MS // 1000
    )
    spec.on_tick(store, block_time)
    run_on_block(spec, store, signed_block)
    block_root = signed_block.message.hash_tree_root()

    return store, signed_block, block_root


def _setup_full_parent(spec, state):
    store, signed_block, block_root = _add_block_to_store(spec, state)

    envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    run_on_execution_payload_envelope(spec, store, envelope)

    assert spec.is_payload_verified(store, block_root)

    return store, block_root, envelope


def _advance_to_proposal_slot(spec, state, store):
    proposal_state = state.copy()
    spec.process_slots(proposal_state, proposal_state.slot + 1)

    proposal_time = store.genesis_time + proposal_state.slot * spec.config.SLOT_DURATION_MS // 1000
    spec.on_tick(store, proposal_time)

    return proposal_state


@with_phases([GLOAS])
@spec_state_test
def test_prepare_execution_payload__extend_payload(spec, state):
    # Give validator[0] 0x01 credentials so the envelope can carry a valid
    # switch-to-compounding request for it. Balance at this point is the
    # default MIN_ACTIVATION_BALANCE, so block_1's withdrawal sweep will
    # not touch it.
    validator_index = 0
    consolidation_request = prepare_switch_to_compounding_request(spec, state, validator_index)
    execution_requests = spec.ExecutionRequests(consolidations=[consolidation_request])

    # Build block_1 with a bid that commits to the requests we will deliver
    # in the envelope. The bid's execution_requests_root must match
    # hash_tree_root(envelope.execution_requests) or envelope verification
    # would reject it.
    store, signed_block, block_root = _add_block_to_store(
        spec, state, execution_requests=execution_requests
    )

    # Build and deliver the envelope while validator[0] still has its
    # post-block_1 balance. payload.withdrawals must hash-equal
    # store.block_states[block_root].payload_expected_withdrawals, which
    # block_1 computed with the unmodified balance.
    envelope = build_signed_execution_payload_envelope(
        spec, state, block_root, signed_block, execution_requests=execution_requests
    )
    run_on_execution_payload_envelope(spec, store, envelope)

    assert spec.is_payload_verified(store, block_root)
    assert spec.should_extend_payload(store, block_root)

    # Advance to the proposal slot before modifying balances. process_slots
    # fills latest_block_header.state_root using the current state hash, so
    # any balance change before this point would make that hash (and the
    # resulting parent_root inside prepare_execution_payload) diverge from
    # block_1's state_root.
    proposal_state = _advance_to_proposal_slot(spec, state, store)

    # Now give validator[0] a balance above MIN_ACTIVATION_BALANCE. Under
    # 0x01 credentials this makes it partially withdrawable. When
    # apply_parent_execution_payload runs inside the extend branch, it
    # flips credentials to 0x02 and drains the excess, so the validator is
    # no longer partially withdrawable. If the spec skipped apply, the
    # validator would still look partially withdrawable and prepared
    # withdrawals would diverge from expected.
    proposal_state.balances[validator_index] = (
        spec.MIN_ACTIVATION_BALANCE + 3 * spec.EFFECTIVE_BALANCE_INCREMENT
    )

    engine = CaptureEngine()
    parent_bid = proposal_state.latest_execution_payload_bid
    payload_id = spec.prepare_execution_payload(
        store=store,
        state=proposal_state,
        safe_block_hash=spec.Hash32(),
        finalized_block_hash=spec.Hash32(),
        suggested_fee_recipient=spec.ExecutionAddress(),
        execution_engine=engine,
    )

    assert payload_id == SAMPLE_PAYLOAD_ID
    assert engine.head_block_hash == parent_bid.block_hash

    expected_state = proposal_state.copy()
    spec.apply_parent_execution_payload(expected_state, envelope.message.execution_requests)
    expected_withdrawals = spec.get_expected_withdrawals(expected_state).withdrawals
    assert engine.payload_attributes.withdrawals == expected_withdrawals

    # Confirm the scenario actually exercises apply_parent_execution_payload:
    # without it, validator[0] would remain 0x01 + excess and contribute a
    # partial withdrawal that is absent once the switch is applied.
    skip_apply_withdrawals = spec.get_expected_withdrawals(proposal_state.copy()).withdrawals
    assert list(skip_apply_withdrawals) != list(expected_withdrawals)


@with_phases([GLOAS])
@spec_state_test
def test_prepare_execution_payload__no_payload_verified(spec, state):
    # Build and process block without execution requests.
    store, _, block_root = _add_block_to_store(spec, state)

    assert not spec.is_payload_verified(store, block_root)
    assert not spec.should_extend_payload(store, block_root)

    proposal_state = _advance_to_proposal_slot(spec, state, store)

    engine = CaptureEngine()
    parent_bid = proposal_state.latest_execution_payload_bid
    payload_id = spec.prepare_execution_payload(
        store=store,
        state=proposal_state,
        safe_block_hash=spec.Hash32(),
        finalized_block_hash=spec.Hash32(),
        suggested_fee_recipient=spec.ExecutionAddress(),
        execution_engine=engine,
    )

    assert payload_id == SAMPLE_PAYLOAD_ID
    assert engine.head_block_hash == parent_bid.parent_block_hash
    assert engine.payload_attributes.withdrawals == proposal_state.payload_expected_withdrawals


@with_phases([GLOAS])
@spec_state_test
def test_prepare_execution_payload__extend_payload_does_not_mutate_state(spec, state):
    store, _, _ = _setup_full_parent(spec, state)
    proposal_state = _advance_to_proposal_slot(spec, state, store)

    state_root_before = proposal_state.hash_tree_root()

    engine = CaptureEngine()
    spec.prepare_execution_payload(
        store=store,
        state=proposal_state,
        safe_block_hash=spec.Hash32(),
        finalized_block_hash=spec.Hash32(),
        suggested_fee_recipient=spec.ExecutionAddress(),
        execution_engine=engine,
    )

    assert proposal_state.hash_tree_root() == state_root_before


@with_phases([GLOAS])
@spec_state_test
def test_prepare_execution_payload__payload_attributes(spec, state):
    store, _, _ = _setup_full_parent(spec, state)
    proposal_state = _advance_to_proposal_slot(spec, state, store)

    engine = CaptureEngine()
    spec.prepare_execution_payload(
        store=store,
        state=proposal_state,
        safe_block_hash=spec.Hash32(),
        finalized_block_hash=spec.Hash32(),
        suggested_fee_recipient=spec.ExecutionAddress(),
        execution_engine=engine,
    )

    attrs = engine.payload_attributes
    assert attrs.timestamp == spec.compute_time_at_slot(proposal_state, proposal_state.slot)
    assert attrs.prev_randao == spec.get_randao_mix(
        proposal_state, spec.get_current_epoch(proposal_state)
    )
    assert attrs.parent_beacon_block_root == proposal_state.latest_block_header.hash_tree_root()
    assert attrs.slot_number == proposal_state.slot
    assert attrs.suggested_fee_recipient == spec.ExecutionAddress()


@with_phases([GLOAS])
@spec_state_test
def test_prepare_execution_payload__block_passes_state_transition(spec, state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    spec.on_tick(store, current_time)

    proposal_state = _advance_to_proposal_slot(spec, state, store)

    engine = CaptureEngine()
    spec.prepare_execution_payload(
        store=store,
        state=proposal_state,
        safe_block_hash=spec.Hash32(),
        finalized_block_hash=spec.Hash32(),
        suggested_fee_recipient=spec.ExecutionAddress(),
        execution_engine=engine,
    )
    prepared_withdrawals = list(engine.payload_attributes.withdrawals)

    block = build_empty_block_for_next_slot(spec, state)
    assert block.slot == proposal_state.slot
    state_transition_and_sign_block(spec, state, block)

    assert list(state.payload_expected_withdrawals) == prepared_withdrawals
