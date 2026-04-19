from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
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


def _setup_full_parent(spec, state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    spec.on_tick(store, current_time)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_time = (
        store.genesis_time + signed_block.message.slot * spec.config.SLOT_DURATION_MS // 1000
    )
    spec.on_tick(store, block_time)
    run_on_block(spec, store, signed_block)
    block_root = signed_block.message.hash_tree_root()

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
    store, block_root, envelope = _setup_full_parent(spec, state)
    assert spec.should_extend_payload(store, block_root)

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
    assert engine.head_block_hash == parent_bid.block_hash

    expected_state = proposal_state.copy()
    spec.apply_parent_execution_payload(
        expected_state, parent_bid, envelope.message.execution_requests
    )
    expected_withdrawals = spec.get_expected_withdrawals(expected_state).withdrawals
    assert engine.payload_attributes.withdrawals == expected_withdrawals


@with_phases([GLOAS])
@spec_state_test
def test_prepare_execution_payload__no_payload_verified(spec, state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    spec.on_tick(store, current_time)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_time = (
        store.genesis_time + signed_block.message.slot * spec.config.SLOT_DURATION_MS // 1000
    )
    spec.on_tick(store, block_time)
    run_on_block(spec, store, signed_block)
    block_root = signed_block.message.hash_tree_root()

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
