"""Shared concrete-input helpers for state-transition materializers."""

from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.attestations import next_epoch_with_attestations
from eth_consensus_specs.test.helpers.block import (
    build_block_and_payload,
    build_empty_block_for_next_slot,
    sign_block,
    transition_unsigned_block,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    compute_and_sign_execution_payload_bid,
    compute_and_sign_execution_payload_envelope,
    compute_el_block_hash,
)
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer.state_preprocessor import (
    common_state_preprocessor,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

BIG = 10_000_000_000  # 10 Gwei, well above MIN_DEPOSIT_AMOUNT


def set_parent_block(spec: Any, state: Any, hash_match: bool) -> None:
    """Set the parent-block state per state_latest_block_hash_match."""
    if hash_match:
        # Parent block full: hashes must match (use a non-zero hash)
        if bytes(state.latest_block_hash) == b"\x00" * 32:
            state.latest_block_hash = spec.Hash32(b"\x01" * 32)
        state.latest_execution_payload_bid.block_hash = state.latest_block_hash
    else:
        # Parent block empty: hashes must differ
        state.latest_block_hash = spec.Hash32(b"\x00" * 32)
        state.latest_execution_payload_bid.block_hash = spec.Hash32(b"\x01" * 32)


def make_base_state(spec: Any, num_validators: int = 64, preprocess: bool = True) -> Any:
    """Build a preprocessed base state (genesis + optional 2-epoch advance)."""
    state = create_genesis_state(
        spec,
        validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * num_validators,
        activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
    )
    state.builders = type(state.builders)()
    state.builder_pending_payments = type(state.builder_pending_payments)()
    state.builder_pending_withdrawals = type(state.builder_pending_withdrawals)()
    if preprocess:
        state = common_state_preprocessor(spec, state)
    return state


def finalize_genesis_builders(spec, state):
    """Return the state at the first free slot after finality passes genesis."""
    with bls_enabled():
        for _ in range(4):
            _, _, state = next_epoch_with_attestations(
                spec, state, fill_cur_epoch=True, fill_prev_epoch=False
            )
    spec.process_slots(state, state.slot + 1)
    return state


def process_execution_requests_after_empty_parent(spec, state, requests):
    """Build a full payload in the current slot and consume it in its child."""
    assert state.latest_block_hash != state.latest_execution_payload_bid.block_hash
    assert all(
        request.amount >= spec.MIN_DEPOSIT_AMOUNT for request in requests.builder_deposits
    ), "EIP-8282 builder deposits must meet the execution-layer minimum"
    with bls_enabled():
        parent, payload = build_block_and_payload(spec, state, execution_requests=requests)
        # The previous block's payload was skipped, so its withdrawals carry forward.
        payload.withdrawals = state.payload_expected_withdrawals.copy()
        payload.block_hash = compute_el_block_hash(spec, payload, state, requests)
        parent.body.signed_execution_payload_bid = compute_and_sign_execution_payload_bid(
            spec, state, payload, execution_requests=requests
        )
        spec.process_block(state, parent)
        parent.state_root = spec.hash_tree_root(state)
        signed_parent = sign_block(spec, state, parent)
        envelope = compute_and_sign_execution_payload_envelope(
            spec, state, spec.hash_tree_root(parent), signed_parent, payload, requests
        )
        spec.verify_execution_payload_envelope(state, envelope, spec.NoopExecutionEngine())

        child = build_empty_block_for_next_slot(spec, state)
        child.body.signed_execution_payload_bid.message.parent_block_hash = payload.block_hash
        child.body.parent_execution_requests = requests
        transition_unsigned_block(spec, state, child)


def exit_builder_after_empty_parent(spec, state, builder_index):
    """Process a builder exit request through the parent payload and its child."""
    builder = state.builders[builder_index]
    requests = spec.ExecutionRequests(
        builder_exits=spec.BuilderExitRequests.of(
            spec.BuilderExitRequest(pubkey=builder.pubkey, source_address=builder.execution_address)
        )
    )
    process_execution_requests_after_empty_parent(spec, state, requests)
    assert state.builders[builder_index].withdrawable_epoch == (
        spec.get_current_epoch(state) + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
    )
